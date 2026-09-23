"""The O-grid's stored binding LIST: its one reader, its one writer, its repair.

Split out of ``topology_ogrid.py`` by #138, which added the repair half and took that
file past the repo's ~500-line standard. The cut is not arbitrary: everything here is
about the STRING a binding is stored as and the positions in it — parsing it, writing
it, asking whether it walks the geometry's own order, listing the positions that no
longer resolve, and replacing one of them. Nothing here knows what a block is. What is
left next door is the family: the derivation, the plan and the document.

Qt-free, like every module in this package.

THE POSITIONS IN THIS LIST ARE BINDING INFORMATION, which is the rule that shapes both
halves of the ticket that added the repair. The ring walks the stored list in the order
it is written, so a repair replaces the id AT ITS POSITION — dropping the broken one and
pushing the rest along would move every wall after it onto a different stretch of
geometry, with every id still resolving and nothing to say so.
"""
from __future__ import annotations

from app.services.topology_binding import BrokenBinding


def parse_binding(text: str, fallback, who: str = "binding") -> tuple:
    """``(ids, problem)`` for a stored ``"0,1,2,3"`` binding list.

    BLANK MEANS "ADOPT WHAT THE GEOMETRY HAS NOW", and that is a state the read-out
    names out loud rather than a silent default. It exists because a model has to be
    usable before anything has captured a binding — a hand-written project file, and
    the moment just after the user picks a geometry. Once captured, the list is the
    binding OF RECORD: a segment that disappears from the geometry is then a refusal
    rather than a shorter ring, which is the difference between a refused projection
    and a mesh that quietly grew a different wall.

    A TOKEN THAT IS NOT A SEGMENT ID IS A REFUSAL, NOT A SKIP. The first draft
    dropped it and carried on, so ``"0,x,2"`` bound two segments where three were
    written and ``"a,b"`` fell all the way back to adopting the whole geometry —
    which is the silently-shorter-ring this whole design exists to make unreachable,
    reintroduced inside the parser that is supposed to prevent it. Review found it;
    it is the reason this returns a sentence rather than a best effort. A DUPLICATE
    is refused for the same reason: one segment at two ring positions is two walls
    on one stretch of geometry, and nothing downstream would say so.

    The ONE parser of this format. The panel asks it too, so "is the held binding
    still good?" and "what does the projection bind?" cannot answer about different
    readings of the same text — they did, and disagreed on ``"0,x,2"``.
    """
    out = []
    for tok in str(text or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = int(tok)
        except ValueError:
            return (), (f"the {who} list contains {tok!r}, which is not a segment "
                        f"id. It is a comma-separated list of the CAD segment ids "
                        f"the walls bind to; clear it to adopt the geometry's own.")
        if v in out:
            return (), (f"the {who} list names segment {v} twice. One segment "
                        f"cannot be two sides of the ring.")
        out.append(v)
    return (tuple(out) if out else tuple(fallback)), ""


def format_binding(ids) -> str:
    """``ids`` as the stored text. The ONE writer of the format, as
    :func:`parse_binding` is its one reader.

    Three places write this string — the capture when a geometry is named, the
    repair when a broken one is re-pointed (#138), and the gates — and a separator
    spelled differently in one of them would make a round trip through the panel
    look like an edit.
    """
    return ", ".join(str(int(v)) for v in ids)


def repair_binding(order, pos: int, seg: int) -> str:
    """The binding that puts segment ``seg`` at ring position ``pos`` (#138).

    A VALID O-GRID BINDING IS A ROTATION OF THE GEOMETRY'S OWN SEGMENT LIST, and
    that is not a convention — it is what the mesher's edge rule forces
    (:func:`cover_problem`). So the only freedom a stored list has is WHERE the ring
    starts, and naming the segment one flagged edge should lie on fixes the whole
    list: this returns ``order`` rotated so ``seg`` lands at ``pos``.

    That is why the repair does not read the broken text at all. A replacement at
    the position — the first thing this function did — left the ring covering only
    part of the outline whenever a split had added a segment, which projects a
    document the mesher then refuses at exit 8 for edge `w<pos>` "binds to segment
    N, so both of its corners must lie on that segment". Trading one refusal for
    another is not a repair, and the user cannot see the difference from the panel.

    The user's own choice is PRESERVED rather than overwritten, which is the whole
    reason this takes a position: adopting the geometry's list outright would drop
    the rotation they picked, so a ring the user had started at segment 7 would
    silently restart at whatever the geometry lists first. Empty when ``seg`` is not
    one of ``order`` — a repair to a segment that is not there is not a repair.
    """
    order = [int(v) for v in order]
    seg = int(seg)
    if not order or seg not in order:
        return ""
    k = (order.index(seg) - int(pos)) % len(order)
    return format_binding(order[k:] + order[:k])


def cover_problem(who: str, g, segs, splits: int, prefix: str) -> tuple:
    """``(edge, problem)`` when a binding does not COVER the outline it wraps.

    THE MESHER'S OWN RULE, MOVED FORWARD TO WHERE THE USER CAN ACT ON IT. A bound
    edge's two corners must both lie on the segment it binds, or on a joint that
    segment shares with its neighbour (``src/MultiBlock.cpp``: "An edge that lies on
    a segment has to start and end on it"). Each wall edge runs from its own
    segment's start to the NEXT bound segment's start, so the next bound segment has
    to be the geometry's next segment — all the way round. A binding that skips one
    is a ring with a hole in it, and the mesher refuses the whole document at exit 8.

    SUPERSEDES #137's "a subset is fine", which was true of
    :func:`order_problem` — a subset walks the geometry's order — and false of the
    document it let through. Measured on a four-segment body: binding `2, 40` of
    `[5, 11, 2, 40]` projected a four-block ring and the mesher refused it by name.
    The claim was never that a subset MESHES; it was that the ORDER check did not
    fire, and nothing else was asking.

    This is also what makes #138's repair a repair: a dropdown that replaced one
    position would leave exactly this hole the moment a CAD split had turned one
    bound segment into two.
    """
    m = len(g.seg_ids)
    pos = [g.seg_ids.index(s) for s in segs]
    n = len(pos)
    for k in range(n):
        if pos[(k + 1) % n] == (pos[k] + 1) % m:
            continue
        missing = g.seg_ids[(pos[k] + 1) % m]
        edge = f"{prefix}{k * splits + splits - 1}"
        return edge, (f"the {who} binding runs segment {segs[(k + 1) % n]} straight after "
                f"segment {segs[k]}, but '{g.spelling}' has segment {missing} "
                f"between them — so edge '{edge}' would have to span two source "
                f"segments, and a bound edge declares ONE, which is how its boundary "
                f"condition is read off the geometry. The ring covers the whole "
                f"outline: bind every segment, in the geometry's order.")
    return "", ""


#: Which stored list is which, as ``(role, model field, geometry field, edge
#: prefix)``. The pairing the O-grid's own ring uses, named once so
#: :func:`broken_bindings` and a future third reader cannot spell it differently.
BINDING_LISTS = (("body", "ogrid_body_segs", "ogrid_body_geom", "w"),
                 ("far field", "ogrid_far_segs", "ogrid_far_geom", "o"))


def broken_bindings(model, ctx) -> tuple:
    """Every stored id this family holds that its geometry no longer carries (#138).

    THE COMPLEMENT OF `plan`'s REFUSAL, NOT A SECOND COPY OF IT. `plan` stops at the
    FIRST problem, because it is answering "can this run?" — one sentence is the
    right answer to that. This answers "what would the user have to fix?", which is
    every broken position at once: repairing them one refusal at a time means a
    generate, a refusal and a return to the panel per broken wall, and the user
    already knows all of the answers.

    SCOPED TO THE ONE THING A DROPDOWN CAN REPAIR. A geometry that is not in the
    mesh's list, an unparseable list, a body that is not closed, a far field inside
    the body — none of those is a wrong SEGMENT, so none is reported here and all of
    them keep the read-out's sentence as their only voice. Reporting them as
    flagged edges would offer a repair that cannot repair them.
    """
    if ctx is None:
        return ()
    try:
        splits = max(1, int(model.ogrid_splits))
    except (TypeError, ValueError):
        splits = 1
    out = []
    for who, field, geom_field, prefix in BINDING_LISTS:
        g = ctx.geometry(getattr(model, geom_field, ""))
        if g is None or not g.seg_ids:
            continue
        held, why = parse_binding(getattr(model, field, ""), (), who)
        if why or not held:
            # A blank list adopts the geometry's own segments and so cannot be
            # broken; a malformed one is refused as a whole string and is not a
            # position a dropdown could re-point.
            continue
        for pos, s in enumerate(held):
            if s in g.spans:
                continue
            base = pos * splits
            out.append(BrokenBinding(
                field=field, who=who, geom=g.spelling, seg=s, pos=pos,
                edges=tuple(f"{prefix}{base + j}" for j in range(splits)),
                choices=tuple(g.seg_ids)))
    return tuple(out)


def order_problem(who: str, g, segs, splits: int, prefix: str) -> tuple:
    """``(edge, problem)`` when a binding list does not WALK the geometry's own order.

    THE EDGE IS RETURNED, NOT RECOVERED FROM THE SENTENCE. `plan` used to do
    ``why.split("edge '")[1].split("'")[0]`` — structured data taken back out of prose,
    in a package whose own rule is that `BindingError` carries the edge as a field so
    the panel can flag it without parsing a message. A reworded sentence turned that
    into an `IndexError`; review named it, and both refusals here now answer in the
    same shape the exception does.

    #137's criterion is that deleting **or reordering** a bound segment is refused
    with the edge named. Deleting is `BindingContext.resolve`'s. Reordering is this:
    the stored list is ORDERED and the ring walks it in that order, so swapping two
    ids keeps every one of them resolvable while sending a wall edge backwards along
    the body. This file's first version argued that a reorder was unreachable
    "because there is no position anywhere in the chain"; the Spec review measured
    otherwise — ``0,2,1,3`` projected a document, and the C++ mesher then refused it
    at exit 8, or worse, the winding check refused it with a FALSE diagnosis about
    the two geometries being wound apart. The argument was wrong: the ORDER of the
    stored list is itself positional information.

    A ROTATION IS FINE — the ring has no first segment. What is refused HERE is a
    walk that goes backwards at more than one joint, which is exactly "the positions
    are not cyclically increasing". A two-entry list cannot distinguish a reversal
    from a rotation and is not refused; stated rather than papered over.

    THIS CHECK'S FIRST VERSION ALSO SAID "a subset is fine", and #138 measured that
    false of the DOCUMENT even though it is true of this function: a subset walks the
    geometry's order, so nothing here fires, and the ring it projects has a hole the
    mesher refuses at exit 8. :func:`cover_problem` is what asks that second question,
    and it runs straight after this one.
    """
    pos = [g.seg_ids.index(s) for s in segs]
    n = len(pos)
    descents = [k for k in range(n) if pos[(k + 1) % n] <= pos[k]]
    if len(descents) <= 1:
        return "", ""
    k = descents[0]
    a, b = segs[k], segs[(k + 1) % n]
    edge = f"{prefix}{((k + 1) * splits) % (n * splits)}"
    return edge, (f"the {who} binding walks segment {b} after segment {a}, but "
            f"'{g.spelling}' runs them the other way round — edge '{edge}' would "
            f"cross the ring. A binding must follow the geometry's own order; a "
            f"rotation of it is fine, a reordering is not.")
