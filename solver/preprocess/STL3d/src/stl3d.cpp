#include <iostream>
#include <tuple>
#include <map>
#include <string>
#include <fstream>
#include <vector>
#include <sstream>
#include <cmath>
#include <set>
#include <stdexcept>
#include <cstdint>
#include "BinIo.hh"
#include "Form.hh"
#include "element.hh"
#include "Vec.hh"
#include "GeoOp.hh"
#include <iterator>
#ifdef _OPENMP
#include <omp.h>
#endif

using namespace std;

//#define ELEM_GC_EPS  1.e-12
#define ELEM_GC_EPS  5.e-10
#define NX_NY_TOL    1.e-12

typedef Vec<3>  point_;


// rewd in vertices that belong to a solid and use it for marking
typedef tuple<double, double, double> vertex_;
typedef map<vertex_, double> vertex_map_;
typedef map<vertex_, int>  center_map_;
typedef center_map_::const_iterator  cmap_itr;
typedef vertex_map_::const_iterator  vmap_itr;
typedef map<pair<double, double>, int> vertex_yz_map_;
typedef vertex_yz_map_::const_iterator  yzmap_itr;


// 3D surface gc
struct sgcoord {
  int elm_id;
  double xi;
  double eta;
  double mag() const { return sqrt(xi*xi+eta*eta); }
};

// mark phi values based on a set of marked solid intersection point in zs
void get_phi(const set<double>& zs, const vector<double>& z, vector<double>& phi) {
  // resize if needed
  phi.resize(z.size());
  if( zs.size() == 0 ) {
    for(int i = 0; i < phi.size(); ++i)
      phi[i] = 0;
    // no intersection markers, mark 0 and return
    return;
  }
  
  set<double>::const_iterator izs = zs.begin();
  double zswitch;
  int mark = 1;
  vector<int> phii(phi.size());
  for(int i = 0; i < z.size(); ++i) {
    zswitch = izs == zs.end() ? 1.e12 : *izs;
    //cout << i << " mark = " << mark << " zsw = " << zswitch << endl;
    if( z[i] >= zswitch ) {
      mark *= -1;
      if( izs != zs.end() ) {
	++izs;
	//cout << "resetting zswitch\n";
      }
    }
    phii[i] = mark;
  }
  // resetting phi values to be 0 and 1
  for(int i = 0; i < phi.size(); ++i)
    phi[i] = phii[i] == 1 ? 0 : 1;

}

// version 2, using z location to determine phi precisely
void get_phi2(const set<double>& zs, const vector<double>& z, vector<double>& phi) {
  // resize if needed
  phi.resize(z.size());
  if( zs.size() == 0 ) {
    for(int i = 0; i < phi.size(); ++i)
      phi[i] = 0;
    // no intersection markers, mark 0 and return
    return;
  }

  vector<double> zsv(zs.size());
  copy(zs.begin(), zs.end(), zsv.begin());
  vector<int> phii(phi.size());
  for(int i = 0; i < z.size(); ++i) {

    double zi = z[i];
    // locate zi
    vector<double>::iterator zloc = lower_bound(zsv.begin(), zsv.end(), zi);
    int iloc = zloc - zsv.begin();
    phii[i] = pow(-1, iloc);
  }
  // resetting phi values to be 0 and 1
  for(int i = 0; i < phi.size(); ++i)
    phi[i] = phii[i] == 1 ? 0 : 1;

}


// calculate triangular projection areas onto y or z-plane and determine the larger one to use
// return value = 1 for y-plane and 2 for z-plane, 0 for 2D
template<int Dim> inline
int calc_proj_dir(const Vec<Dim>* vtx) {
  if(Dim == 2)
    return 0;
  Vec<Dim> p1 = vtx[0];
  Vec<Dim> p2 = vtx[1];
  Vec<Dim> p3 = vtx[2];
  Vec<Dim> p4 = p1, p5 = p2, p6 = p3;
  p1[2] = 0;
  p2[2] = 0;
  p3[2] = 0;
  double Ay = GeoOp<Dim>::area(p1, p2, p3);
  p4[3] = 0;
  p5[3] = 0;
  p6[3] = 0;
  double Az = GeoOp<Dim>::area(p4, p5, p6);
  return Ay > Az ? 1 : 2;
}

// compute gc for a triangular (surface) eleemnt using the projection method
template<int Dim> inline
void surfGC3s(const Vec<Dim>& p, const Vec<Dim>* vtx, Vec<Dim>& gc) {
  const Vec<Dim>& v0 = vtx[0];
  const Vec<Dim>& v1 = vtx[1];
  const Vec<Dim>& v2 = vtx[2];
  int dir = calc_proj_dir(vtx);

  if( dir == 1 ) {
    double detm = (v1[1] - v0[1]) * (v2[3] - v0[3]) -
	(v2[1] - v0[1]) * (v1[3] - v0[3]);
    if( abs(detm) < 1.e-16 ) {
	cerr << " detm = 0 in surfGC3s fro dir = 1\n";
	detm = 1.e-16;
	gc[1] = -1;  // returns an out of domain gc so that it can be screened out
	gc[2] = 0;
	return;
	//exit(1);
    }
    double xi1 = ((p[1] - v0[1]) * (v2[3] - v0[3]) -
		    (p[3] - v0[3]) * (v2[1] - v0[1])) / detm;
    double xi2 = ((v1[1] - v0[1]) * (p[3] - v0[3]) -
		    (v1[3] - v0[3]) * (p[1] - v0[1])) / detm;
    gc[1] = xi1;
    gc[2] = xi2;
  }
  else {
    double detm = (v1[1] - v0[1]) * (v2[2] - v0[2]) -
	(v2[1] - v0[1]) * (v1[2] - v0[2]);
    if( abs(detm) < 1.e-16 ) {
	cerr << " detm = 0 in surfGC3s fro dir = 2\n";
	detm = 1.e-16;
	gc[1] = -1;  // returns an out of domain gc so that it can be screened out
	gc[2] = 0;
	return;
	//exit(1);
    }
    double xi1 = ((p[1] - v0[1]) * (v2[2] - v0[2]) -
		    (p[2] - v0[2]) * (v2[1] - v0[1])) / detm;
    double xi2 = ((v1[1] - v0[1]) * (p[2] - v0[2]) -
		    (v1[2] - v0[2]) * (p[1] - v0[1])) / detm;
    gc[1] = xi1;
    gc[2] = xi2;
  }
}


double distance(const vertex_& p1, const vertex_& p2) {
  double x1 = get<0>(p1);
  double y1 = get<1>(p1);
  double z1 = get<2>(p1);
  double x2 = get<0>(p2);
  double y2 = get<1>(p2);
  double z2 = get<2>(p2);
  return sqrt((x2-x1)*(x2-x1) + (y2-y1)*(y2-y1) + (z2-z1)*(z2-z1));
}

bool within_Striangle(const point_& gc) {
    double xi1 = gc[1];
    double xi2 = gc[2];
    double xi0 = 1. - xi1 - xi2;
    double eps = ELEM_GC_EPS;

    if( xi0 < -eps || xi0 > 1. + eps )
      return false;
    if( xi1 < -eps || xi1 > 1. + eps )
      return false;
    if( xi2 < -eps || xi2 > 1. + eps )
      return false;
    return true;
}

// Return the size of a file in bytes, or -1 if it cannot be opened / stat'd.
static long long file_size_bytes(const string& fn) {
  ifstream in(fn.c_str(), std::ios::binary | std::ios::ate);
  if( !in.is_open() )
    return -1;
  std::streampos pos = in.tellg();
  if( pos < 0 )
    return -1;
  return static_cast<long long>(pos);
}

// Auto-detect whether an STL file is ASCII or binary without blocking on stdin.
// A binary STL is exactly 84 + 50*count bytes (80-byte header + 4-byte uint32
// count + 50 bytes per triangle); when the size matches that layout for the
// declared count we treat it as binary. Otherwise, if the file begins with the
// ASCII token "solid" it is treated as ASCII. Returns true for ASCII.
static bool detect_ascii_stl(const string& fn) {
  long long sz = file_size_bytes(fn);
  if( sz < 0 )
    throw std::runtime_error("detect_ascii_stl: cannot open STL file: " + fn);

  // Try the binary layout first: read the 4-byte little-endian count at offset 80.
  if( sz >= 84 ) {
    ifstream in(fn.c_str(), std::ios::binary);
    if( in.is_open() ) {
      in.seekg(80, std::ios::beg);
      uint32_t count = 0;
      if( in.read(reinterpret_cast<char*>(&count), 4) ) {
        long long expected = 84LL + 50LL * static_cast<long long>(count);
        if( expected == sz )
          return false;  // binary layout matches exactly
      }
    }
  }

  // Fall back to the ASCII magic token "solid" at the start of the file.
  ifstream in(fn.c_str(), std::ios::binary);
  if( in.is_open() ) {
    char head[6] = {0};
    in.read(head, 5);
    string tok(head, static_cast<size_t>(in.gcount()));
    if( tok.rfind("solid", 0) == 0 )
      return true;  // ASCII STL
  }

  // Neither an exact binary layout nor a "solid" header: default to binary,
  // which validates the triangle count against the file size and reports a
  // clear error if the file is corrupt.
  return false;
}

class STLobject {

  vector<vertex_> allvtx;
  vector<point_> vvtx_;
  vector<point_> normal_;
  vector<vector<int> > conn;
  vector<element> elements_;
  vector<point_> centers_;
  vector<point_> elem_eqs_;   // plane equations ax + by + cz + d = 0
  vector<double> elem_eqs_d_;
  vector<double> elem_mins_;
  vector<double> elem_maxs_;
  
  // cell center database
  center_map_    ctr_db_;
  map<double, cmap_itr>  xloc_db;
  

public:

  double xmin, xmax, ymin, ymax, zmin, zmax, dx00;
  
  STLobject(const string& fn, bool ascii = true) {
    vector<vector<vertex_> > triangles;
    if(ascii) {
      ifstream in(fn.c_str());
      if(! in.is_open() ) {
	throw std::runtime_error("STLobject: error opening file: " + fn);
      }
      string s, key, dum;
      double x, y, z;
      vector<vertex_> vtxi(3);
      getline(in, s);   // first line, starting with solid...
      while(true) {
	getline(in, s);   // either facet normal or endsolid
	istringstream ist0(s);
	ist0 >> key;
	if( key == "endsolid")
	  break;
	// read in normal and save it
	istringstream ist1(s);
	string dum1, dum2;
	ist1 >> dum1 >> dum2 >> x >> y >> z;
	normal_.push_back(point_ (x, y, z));
	getline(in, s);   // outer loop
	for(int i = 0; i < 3; ++i) {
	  // read 3 vertices
	  getline(in, s);
	  istringstream isti(s);
	  isti >> dum >> x >> y >> z;
	  vtxi[i] = make_tuple(x, y, z);
	  //cout << " point " << x << " " << y << " " << z << endl;
	}
	triangles.push_back(vtxi);
	getline(in, s);    // endloop
	getline(in, s);    // endfacet
      }
    }
    else {
      // binary format
      BinRead bf(fn, true);  // force open
      string title(80, ' ');
      if( !bf.read(&title[0], 80) )
	throw std::runtime_error("binary STL: failed to read 80-byte header: " + fn);
      int num_triangles;
      if( !bf.read(num_triangles) )
	throw std::runtime_error("binary STL: failed to read triangle count: " + fn);
      cout << " file tille = " << title << " with " << num_triangles << " triangles\n";

      // Never trust the header count blindly: a corrupt/truncated file can
      // declare billions of triangles and cause unbounded allocation / OOM /
      // hang. Reject non-positive counts and require the file size to match the
      // binary STL layout exactly (84 + 50*num_triangles bytes).
      if( num_triangles <= 0 )
	throw std::runtime_error("binary STL: non-positive triangle count (corrupt file): " + fn);
      long long sz = file_size_bytes(fn);
      if( sz < 0 )
	throw std::runtime_error("binary STL: cannot determine file size: " + fn);
      long long expected = 84LL + 50LL * static_cast<long long>(num_triangles);
      if( sz != expected ) {
	std::ostringstream msg;
	msg << "binary STL: file size (" << sz << " bytes) does not match declared "
	    << num_triangles << " triangles (expected " << expected
	    << " bytes = 84 + 50*count) -- corrupt or truncated file: " << fn;
	throw std::runtime_error(msg.str());
      }

      vector<float> v(3);
      vector<vertex_> vtxi(3);
      short attri;
      for(int i = 0; i < num_triangles; ++i) {
	if( !bf.read(&v[0], 3) )   // normal vector
	  throw std::runtime_error("binary STL: unexpected end of file reading normals: " + fn);
	normal_.push_back(point_ (v[0], v[1], v[2]));
	//cout << i << " v = " << v[0] << " " << v[1] << " " << v[2] << endl;
	for(int k = 0; k < 3; ++k) {
	  if( !bf.read(&v[0], 3) )   // vertex
	    throw std::runtime_error("binary STL: unexpected end of file reading vertices: " + fn);
	  //cout << i << " vv = " << v[0] << " " << v[1] << " " << v[2] << endl;
	  vtxi[k] = make_tuple(v[0], v[1], v[2]);
	}
	triangles.push_back(vtxi);
	if( !bf.read(attri) )   // attribute
	  throw std::runtime_error("binary STL: unexpected end of file reading attributes: " + fn);
      }
    }

    cout << "Read in " << triangles.size() << " triangles\n";

    // An empty / zero-triangle STL leaves ctr_db_ and xloc_db empty; the range
    // checks below (ctr_db_.begin()/rbegin(), xloc_db.begin()) would then
    // dereference end() and crash. Bail out with a clear message first.
    if( triangles.empty() )
      throw std::runtime_error("empty or zero-triangle STL: " + fn);

    // processing vertices and build connectivity
    map<vertex_, int> vtx_db;
    set<vertex_> vtx_set;
    for(int i = 0; i < triangles.size(); ++i) 
      for(int k = 0; k < triangles[i].size(); ++k)
	vtx_set.insert(triangles[i][k]);
    
    int count = 0;
    for(set<vertex_>::const_iterator i = vtx_set.begin(); i != vtx_set.end(); ++i) {
      vtx_db.insert(make_pair(*i, count));
      allvtx.push_back(*i);
      ++count;
    }
    // ready for look up for connectivity
    for(int i = 0; i < triangles.size(); ++i) {
      vector<int> nvtx;
      element el;
      for(int k = 0; k < triangles[i].size(); ++k) {
	map<vertex_, int>::iterator iv = vtx_db.find(triangles[i][k]);
	if( iv == vtx_db.end() ) {
	  std::ostringstream msg;
	  msg << "STLobject: failed to locate " << i << "-th triangle, " << k
	      << "-th vertex = " << get<0>(triangles[i][k]) << " "
	      << get<1>(triangles[i][k]) << " " << get<2>(triangles[i][k]);
	  throw std::runtime_error(msg.str());
	}
	nvtx.push_back(iv->second);
      }
      for(int k = 0; k < nvtx.size(); ++k)
	el.push_back(nvtx[k]);
      conn.push_back(nvtx);
      elements_.push_back(el);
    }
    // copy vertex over to Vec<3> for better processing
    for(int i = 0; i < allvtx.size(); ++i)
      vvtx_.push_back(allvtx[i]);

    // locate element centers
    for(int i = 0; i < elements_.size(); ++i) {
      element& el = elements_[i];
      vector<point_> vtxi;
      for(int k = 0; k < el.size(); ++k)
	vtxi.push_back(vvtx_[el[k]]);
      point_ center = GeoOp<3>::triang_center(&vtxi[0]);
      centers_.push_back(center);
    }

    set<double> xloc, yloc, zloc;
    // build cell center database for later lookup
    for(int i = 0; i < elements_.size(); ++i) {
      point_ c = centers_[i];
      ctr_db_.insert(make_pair(make_tuple(c[1], c[2], c[3]), i));
      xloc.insert(c[1]);
      yloc.insert(c[2]);
      zloc.insert(c[3]);
    }
    
    /*
    for(cmap_itr i = ctr_db_.begin(); i != ctr_db_.end(); ++i) {
      vertex_ p = i->first;
      double x = get<0>(p);
      if(x > -5.25 && x < -5.)
	cout << x << " " << get<1>(p) << " " << get<2> (p) << " " << i->second <<endl;
    }
    */
    
    // store x coordinate for searching
    vector<double> xv;
    for(set<double>::iterator i = xloc.begin(); i != xloc.end(); ++i)
      xv.push_back(*i);
    
    // check ranges
    vertex_ p0 = ctr_db_.begin()->first;
    vertex_ pN = ctr_db_.rbegin()->first;
    cout << " first point = " << get<0>(p0) << " " << get<1>(p0) << " " << get<2>(p0) << endl;
    cout << " last point = " << get<0>(pN) << " " << get<1>(pN) << " " << get<2>(pN) << endl;
#if 0
    // set ranges, assuming a rectangular domain with cartesian type meshes
    xmin = get<0>(p0);
    xmax = get<0>(pN);
    ymin = get<1>(p0);
    ymax = get<1>(pN);
    zmin = get<2>(p0);
    zmax = get<2>(pN);
#endif
    // Domain extents MUST come from the vertices, not the element centers.
    // trace_ray() culls any ray with (x < xmin || x > xmax), and a triangle
    // center sits strictly inside the surface, so a center-based box shrinks the
    // culling window below the true geometry -- badly for a coarse or fan-shaped
    // tessellation (e.g. an ear-clipped 2D profile) whose centroids never reach
    // the real extent, which then clips off whole regions of the object.
    xmin = ymin = zmin =  1.e300;
    xmax = ymax = zmax = -1.e300;
    for(int i = 0; i < vvtx_.size(); ++i) {
      const point_& v = vvtx_[i];
      xmin = min(xmin, v[1]); xmax = max(xmax, v[1]);
      ymin = min(ymin, v[2]); ymax = max(ymax, v[2]);
      zmin = min(zmin, v[3]); zmax = max(zmax, v[3]);
    }

    for(int i = 0; i < xv.size(); ++i) {
      vertex_ pi = make_tuple(xv[i], ymin, zmin);
      cmap_itr ipi = ctr_db_.lower_bound(pi);
      xloc_db.insert(make_pair(xv[i], ipi));
    }

    for(int i = 0; i < elements_.size(); ++i) {
      double smin, smax;
      side_lengths(elements_[i], smin, smax);
      elem_mins_.push_back(smin);
      elem_maxs_.push_back(smax);
    }

    int i0 = xloc_db.begin()->second->second;
    dx00 = elem_maxs_[i0];  // use max element side length as a reference
#if 0
    // calculate plane equations
    for(int i = 0; i < elements_.size(); ++i) {
      double d;
      point_ eqn;
      get_plane_eqs(i, eqn, d);
      elem_eqs_.push_back(eqn);
      elem_eqs_d_.push_back(d);
    }
#endif
    // ready for lookup
  }

  // determin if (x, y) line intersects with element i or not, if yes, return intersecting zs
  bool intersect_element(double x, double y, int i, double& zs) const {
    point_ norm = normal_[i];
    
    point_ v0 = vvtx_[elements_[i][0]];  // first vertex
    double x0 = v0[1];
    double y0 = v0[2];
    double z0 = v0[3];
#if 1    
    if( fabs(norm[3]) < NX_NY_TOL ) {
      //cout << "x y = " << x << " " << y << endl;
      //cout << "elem x y = " << x0 << " " << y0 << endl;
      //cout << "  center x y = " << centers_[i][1] << " " << centers_[i][2] << endl;
      //if( fabs(x - x0) > NX_NY_TOL || fabs(y - y0) > NX_NY_TOL)
      //	return false;  // no intersection
      // this element plane is parallel to the (x, y) line
      // use equation to solver for zs
      point_ eqn;
      double d;
      get_plane_eqs(i, eqn, d);
      //cout << " d = " << d << " eqn = " << eqn << endl;
      if( fabs(eqn[3]) < NX_NY_TOL) {
	//cout << "intersect_element = false " << eqn << " d = " << d << " ax+by -d = " << eqn[1]*x+eqn[2]*y-d <<  endl;
	return false;
      }
      zs = (d - (eqn[1] * x + eqn[2] * y)) / eqn[3];
      //cout << "nz zero " << x << " " << y << " " << zs << endl;
      return true;
      //return false;  // if (x, y) on the plane, still return false bec. z can't be determined
    }

    // use dot product to calculate z
    zs = z0 - (norm[1] * (x - x0) + norm[2] * (y - y0))/norm[3];
    return true;
#endif    
#if 0
    // now solve plane equation and find intersect
    const point_& eqn = elem_eqs_[i];
    double d = elem_eqs_d_[i];
    zs = (d - (eqn[1] * x + eqn[2] * y)) / eqn[3];
    return true;
#endif
    
  }

  void get_vertexEL(int i, vector<point_>& vtx) const {
    const element& el = elements_[i];
    vector<point_> (el.size()).swap(vtx);
    for(int k = 0; k < vtx.size(); ++k)
      vtx[k] = vvtx_[el[k]];
  }

  // calcualte general coordinates of point p within element i
  void get_gc_elem(const point_& p, int i, point_& gc) const {
    const element& el = elements_[i];
    vector<point_> vtx;
    get_vertexEL(i, vtx);
    surfGC3s(p, &vtx[0], gc);
  }

  bool within_element(const point_& p, int i, point_& gc) const {
    get_gc_elem(p, i, gc);
    return within_Striangle(gc);
  }
  
  void side_lengths(const element& el, double& smin, double& smax) const {
    set<double> slen;
    for(int k = 0; k < el.size(); ++k) {
      int kp1 = k == el.size() - 1 ? 0 : k + 1;
      double d = vabs(vvtx_[el[kp1]] - vvtx_[el[k]]);
      slen.insert(d);
    }
    smin = *slen.begin();
    smax = *slen.rbegin();
  }

  void get_plane_eqs(int i, point_& eqn, double& d) const {
    const element& el = elements_[i];
    vector<point_> vtx;
    get_vertexEL(i, vtx);
    d = 1; // constant if non singular matrix
    bool success = GeoOp<3>::get_seg_eqn(vtx[0], vtx[1], vtx[2], eqn);
    if( !success ) {
	// determinant is zero, the plane must passes (0, 0, 0)
	// use face normal to set up equations
	cout << " equation determinant is zero for element " << i << endl;
	eqn = normal_[i];
	d = 0;
    }
  }

  bool within_plane(const point_& p, int i) const {
    const point_& eqn = elem_eqs_[i];
    double a = eqn[1];
    double b = eqn[2];
    double c = eqn[3];
    double tol = a * p[1] + b * p[2] + c * p[3] - 1;
    return fabs(tol) < 1.e-12;
  }

  bool within_plane(const vertex_& p, int i) const {
    const point_& eqn = elem_eqs_[i];
    double a = eqn[1];
    double b = eqn[2];
    double c = eqn[3];
    double tol = a * get<0>(p) + b * get<1>(p) + c * get<2>(p) - 1;
    return fabs(tol) < 1.e-12;
  }
  // First element-center strip at or after x in xloc_db, CLAMPED so the result
  // is always usable.
  //
  // xloc_db is keyed by element CENTER x, while xmin/xmax come from the
  // VERTICES -- a centroid sits strictly inside the surface, so the largest
  // center x is below xmax. A ray in that strip passes trace_ray()'s range
  // check yet has no key at or after it, so a plain lower_bound() returns
  // end() and dereferencing it is undefined: that is what segfaulted on a flat
  // 2D profile, whose fan tessellation leaves every centroid far inside the
  // extent (max center x 5.856 vs xmax 6.070), killing the last ~30 of 128
  // x-slices. Clamp instead of dereferencing:
  //   want_last = true  -> the last (nearest) strip, for a value that must name
  //                        a real element: the reference length, a range start
  //   want_last = false -> ctr_db_.end(), the exclusive end of such a range
  // xloc_db is never empty here (the constructor rejects a zero-triangle STL,
  // and trace_ray() guards it anyway).
  cmap_itr ctr_strip_at_or_after(double x, bool want_last) const {
    map<double, cmap_itr>::const_iterator it = xloc_db.lower_bound(x);
    if( it != xloc_db.end() )
      return it->second;
    return want_last ? prev(xloc_db.end())->second : ctr_db_.end();
  }

// returns an out of domain gc so that it can be screened out
  // trace ray defined by (x, y) and return false if not intersect
  // with the object, if it does intersect, return an array of
  //  intersections defined by a z-array
  bool trace_ray(double x, const vector<double>& y, vector<set<double> >& zs, bool all_search = false) const {
    zs.resize(y.size());
    // check if out of range
    if( xloc_db.empty() || x < xmin || x > xmax ) {
      //cout << "x = " << x << " is out of range\n";
      return false;
    }
    // extract candidate elements first
    int index = ctr_strip_at_or_after(x, true)->second;
    double dx = elem_maxs_[index];
    double expandf = 100;
    double xip = min(x + expandf*dx, xmax);
    double xim = max(x - expandf*dx, xmin);
    cmap_itr i1 = ctr_strip_at_or_after(xim, true);
    cmap_itr i2 = ctr_strip_at_or_after(xip, false);
    if( all_search) {
      i1 = ctr_db_.begin();
      i2 = ctr_db_.end();
    }

    //cout << "set range xim = " << xim << "  to xip " << xip << endl;
    //cout << "selected x range = " << get<0>(i1->first) << " to " << get<0>(i2->first) << endl;
    vector<int> candidates;
    set<double> ysloc, zsloc;
    for(cmap_itr i = i1; i != i2; ++i) {
      candidates.push_back(i->second);
      ysloc.insert(get<1>(i->first));
      zsloc.insert(get<2>(i->first));
    }
    //cout << "candidates size = " << candidates.size() << endl;

    if( candidates.empty() )
      // The window landed between strips (or past the last one): there is
      // nothing to intersect on this slice, and the y/z bounds below would
      // dereference an empty set.
      return false;

    double ypmin = *ysloc.begin() - dx;  // add a small buffer
    double ypmax = *ysloc.rbegin() + dx;
    double zpmin = *zsloc.begin() - dx;  // add a small buffer
    double zpmax = *zsloc.rbegin() + dx;
    //cout << " max y&z = " << ypmin << " " << ypmax << " " << zpmin << " " << zpmax << endl;

    for(int i = 0; i < y.size(); ++i) {
      double yi = y[i];
      if(yi < ypmin || yi > ypmax)
	// out of range, do nothing
	continue;
      // check if any intersections with the
      vector<int> elems;

      // now use accruate search
      //cout << "x, y = " << x << " " << yi << endl;

      for(int it = 0; it < candidates.size(); ++it) {
	int index = candidates[it];
	double zint;
	const point_& ctr = centers_[index];
	bool intersect = intersect_element(x, yi, index, zint);
	if( !intersect )
	  // do nothing
	  continue;
	if( zint < zpmin || zint > zpmax )
	  continue;  // out of range, skip

	//cout << intersect << " ints = " << x << " " << yi << " " << zint << endl;
	//cout << index << " with center = " << ctr << endl;
	
	// check if intersection point is within the element
	point_ gc;
	point_ ps(x, yi, zint);
	if( within_element(ps, index, gc) ) {
	  zs[i].insert(zint);
	  //cout << gc << " within element " << index << " pt = " << ps << endl;
	}
	//else
	//  cout << index << " out gc = " << gc << endl;
      }
      //cout << "Plane x = " << x << " y = " << yi << " has " << zs[i].size() << " intersections with the solid surface\n";
      //copy(zs[i].begin(), zs[i].end(), ostream_iterator<double>(cout, " "));
      //cout << endl;
    }

    // check to see if any intersection points
    bool intersect = false;
    for(int i = 0; i < zs.size(); ++i)
      if( zs[i].size() != 0 ) {
	intersect = true;
	break;
      }
    return intersect;
  }


  void write_tecplot(const string& fn) const {
    ofstream out(fn.c_str());

    out << "Title = \" Unstructured mesh output\"\n";
    out << "variables = \"x\", \"y\", \"z\"\n";
    out << "zone N = " << allvtx.size() << " E = "
	<< conn.size() << " ZONETYPE= FETRIANGLE, DATAPACKING=POINT\n";
    
    Form<double> rfmt;
    rfmt.setfmt("16.7e");
    for(int i = 0; i < allvtx.size(); ++i)
      out << rfmt(get<0>(allvtx[i])) << rfmt(get<1>(allvtx[i])) << rfmt(get<2>(allvtx[i])) << endl;

    for(int i = 0; i < conn.size(); ++i) {
      for(int k = 0; k < conn[i].size(); ++k)
	out << conn[i][k] + 1 << " ";
      out << endl;
    }

    out.close();
    
  }
  
};


int main() {
 try {
#if 0
  STLobject stl1("teapot.stl", true);
  stl1.write_tecplot("teapot_tec.dat");

  STLobject stl2("prop.stl", false);
  stl2.write_tecplot("prop_tec.dat");

  //STLobject stl3("cube.stl", false);
  //stl3.write_tecplot("cube_tec.dat");

  //STLobject stl4("Utah_teapot.stl", false);
  //stl4.write_tecplot("Utah_teapot_tec.dat");

  STLobject stl5("plane.stl", false);
  stl5.write_tecplot("plane_tec.dat");

  STLobject stl6("turbine.stl", true);
  stl6.write_tecplot("turbine_tec.dat");
#endif
  string fn;
  cout << "Enter STL file name = ";
  cin >> fn;
  cout << endl;
  // Auto-detect ASCII vs binary from the file itself instead of blocking on an
  // interactive y/n prompt (this tool runs headless in the pipeline).
  bool ascii = detect_ascii_stl(fn);
  cout << "Detected STL format: " << (ascii ? "ASCII" : "binary") << endl;
  string case_fn;
  cout << "Enter desired output case name = ";
  cin >> case_fn;
  cout << endl;

  string fn_stl = case_fn + "_stl_tec.dat";
  string fn_out = case_fn + "_phi_tec.dat";
  cout << "Output " << fn_stl << " for the STL object Tecplot file\n";
  cout << "      " << fn_out << " for the mesh + phi marking Tecplot file\n\n";

  STLobject sobj(fn, ascii);
  sobj.write_tecplot(fn_stl);

  cout << "The read in STL object has the following coordinate ranges:\n";
  cout << " x range = " << sobj.xmin << " - " << sobj.xmax << endl;
  cout << " y range = " << sobj.ymin << " - " << sobj.ymax << endl;
  cout << " z range = " << sobj.zmin << " - " << sobj.zmax << endl;

  // A planar-in-z STL (a 2D profile exported as a flat z=const sheet) yields a
  // single ray crossing per interior (x, y). The z-ray parity in get_phi() would
  // turn that lone crossing into a half-space split -- or, when z=const lands on
  // a grid plane, a floating-point tie -- that no grid refinement can fix. Detect
  // it here and mark by in-plane containment instead (see the slice loop below):
  // the ray hits the sheet iff (x, y) is inside the profile, so the whole
  // z-column is solid there. The threshold is relative to the in-plane extent so
  // the test is scale-invariant; it falls back to an absolute 1e-9 when the STL
  // is also degenerate in x and y (extent 0).
  double zext  = sobj.zmax - sobj.zmin;
  double xyext = max(sobj.xmax - sobj.xmin, sobj.ymax - sobj.ymin);
  bool flat_stl = zext <= 1.e-9 * (xyext > 0. ? xyext : 1.0);
  if( flat_stl )
    cout << "\n Detected a flat (planar-in-z) STL -> 2D column-fill marking "
            "(z-ray parity skipped)." << endl;

  cout << "Enter the Cartesian domain size (xmin, xmax, ymin, ymax, zmin, zmax) :\n";
  double xmin, xmax, ymin, ymax, zmin, zmax;
  cin >> xmin >> xmax >> ymin >> ymax >> zmin >> zmax;
  cout << endl;

  cout << "Enter desired number of mesh points (Nx, Ny, Nz): \n";
  int Nx, Ny, Nz;
  cin >> Nx >> Ny >> Nz;
  cout << endl;
  cout << "\n Users can select either close x-range(answer n in the following question) or all-element search (y) \n";
  cout << "Perform all elements search (y/n) ? \n";
  string as_yn;
  cin >> as_yn;
  cout << endl;
  bool all_search = as_yn == "y" || as_yn == "Y" ? true : false;
  
  // construct the mesh
  vector<double> xg(Nx), yg(Ny), zg(Nz);
  double dx = (xmax - xmin) / static_cast<double>(Nx - 1);
  double dy = (ymax - ymin) / static_cast<double>(Ny - 1);
  double dz = (zmax - zmin) / static_cast<double>(Nz - 1);
  for(int i = 0; i < Nx; ++i)
    xg[i] = xmin + i * dx;
  for(int i = 0; i < Ny; ++i)
    yg[i] = ymin + i * dy;
  for(int i = 0; i < Nz; ++i)
    zg[i] = zmin + i * dz;

  vector<vector<vector<double> > > x_grid(Nx);
  vector<vector<vector<double> > > y_grid(Nx);
  vector<vector<vector<double> > > z_grid(Nx);
  vector<vector<vector<double> > > phi(Nx);
  for(int i = 0; i < Nx; ++i) {
    x_grid[i].resize(Ny, vector<double> (Nz));
    y_grid[i].resize(Ny, vector<double> (Nz));
    z_grid[i].resize(Ny, vector<double> (Nz));
    phi[i].resize(Ny, vector<double> (Nz));
  }
#if 0  
  vector<set<double> > zs;
  vector<double> ytmp;
  ytmp.push_back(0.0829008);
  ytmp.push_back(0.0998473);
  ytmp.push_back(0.116794);
  sobj.trace_ray(11.675, ytmp, zs, all_search);
  
  for(int j = 0; j < ytmp.size(); ++j) {
    vector<double>phij;
    get_phi2(zs[j], zg, phij);
    cout << j << " y = " << ytmp[j] << endl;
    copy(phij.begin(), phij.end(), ostream_iterator<double>(cout, " "));
    cout << endl;
  }
#endif  
  
#if 1
  // The x-slices are independent (iteration i writes only phi[i] / *_grid[i])
  // and trace_ray()/get_phi() touch no shared mutable state, so the slice loop
  // is parallelised with OpenMP. Without -fopenmp the pragmas are ignored and
  // this stays a correct serial loop. A guarded counter keeps the
  // "<n> tracing" progress lines monotonic for the GUI even though slices
  // finish out of order.
  int n_done = 0;
#ifdef _OPENMP
  cout << "OpenMP: ray tracing on up to " << omp_get_max_threads()
       << " thread(s) (OMP_NUM_THREADS)" << endl;     // endl: flush so the GUI sees it live
  double _t0 = omp_get_wtime();
#else
  cout << "serial build (no OpenMP)" << endl;
#endif
#pragma omp parallel for schedule(dynamic)
  for(int i = 0; i < Nx; ++i) {
    vector<set<double> > zs;
    sobj.trace_ray(xg[i], yg, zs, all_search);
    for(int j = 0; j < yg.size(); ++j) {
      //cout << j << " zs size = " << zs[j].size() << endl;
      vector<double> phij;
      if( flat_stl )
        // 2D sheet: a non-empty zs means the vertical ray hit the sheet, i.e.
        // (x, y) is inside the profile -> fill the whole z-column solid. This is
        // independent of the z-grid, so it is stable at any mesh density and
        // sidesteps the lone-crossing parity ambiguity in get_phi().
        phij.assign(zg.size(), zs[j].empty() ? 0.0 : 1.0);
      else
        get_phi(zs[j], zg, phij);
      for(int k = 0; k < zg.size(); ++k) {
	phi[i][j][k] = phij[k];
	x_grid[i][j][k] = xg[i];
	y_grid[i][j][k] = yg[j];
	z_grid[i][j][k] = zg[k];
      }
    }
#pragma omp critical
    {
      // endl flushes so the GUI receives progress live over the pipe (a bare
      // '\n' is block-buffered and would arrive only in bursts / at exit).
      cout << ++n_done << " tracing" << endl;
    }
  }
#ifdef _OPENMP
  cout << "ray tracing wall time: " << (omp_get_wtime() - _t0) << " s" << endl;
#endif

  ofstream tecout(fn_out.c_str());
  tecout << "title = \"STL object marked grid\"\n";
  tecout << "variables = x, y, z, phi\n";
  tecout << "zone i = " << Nx << " j = " << Ny << " k = " << Nz << " f=point\n";

  for(int k = 0; k < Nz; ++k) 
    for(int j = 0; j < Ny; ++j) 
      for(int i = 0; i < Nx; ++i)
	tecout << x_grid[i][j][k] << " " << y_grid[i][j][k] << " " << z_grid[i][j][k] << " " << phi[i][j][k] << "\n";
  
  tecout.close();
#endif
  return 0;
 }
 catch(const std::exception& e) {
   // A CLI user still sees "print error, exit nonzero", but the failure is now
   // recoverable (thrown, not exit()) so subprocess callers can handle it.
   cerr << "STL3d error: " << e.what() << endl;
   return 1;
 }
}
