#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Translation of the AMC::Boite Perl module into Python 3.
"""

import math


# ------------------------------------------------------------------------------
# Placeholder debug function. Replace with logging if desired.
# ------------------------------------------------------------------------------
def debug(msg):
    """
    Simple debug logger. 
    """
    # Example: print(msg)
    pass


# ------------------------------------------------------------------------------
# We rename these to avoid clashing with Python's built-in max() and min().
# If you truly want to override them, name them 'max'/'min' at your own risk.
# ------------------------------------------------------------------------------
def amc_max(*values):
    """
    Equivalent to AMC::Boite::max in Perl.
    Returns the largest value among the arguments.
    """
    if not values:
        raise ValueError("amc_max() needs at least one value.")
    m = values[0]
    for val in values[1:]:
        if val > m:
            m = val
    return m


def amc_min(*values):
    """
    Equivalent to AMC::Boite::min in Perl.
    Returns the smallest value among the arguments.
    """
    if not values:
        raise ValueError("amc_min() needs at least one value.")
    m = values[0]
    for val in values[1:]:
        if val < m:
            m = val
    return m


class AMCBox:
    """
    Python translation of the AMC::Boite package.
    """

    def __init__(self, **kwargs):
        """
        Equivalent to 'sub new { ... }' in Perl.
        Creates a new box object with default attributes, 
        then merges any given kwargs if they match known keys.
        """
        # In Perl: 
        #   my $self = { coins => [[], [], [], []], droite => 1, ...}
        #   bless $self;
        self.coins = [[], [], [], []]  # four corners
        self.droite = 1  # whether the box is "straight" (aligned)

        # Additional ephemeral attribute
        self.point_actuel = 0

        # Merge recognized keys from **kwargs
        for k in kwargs:
            if hasattr(self, k):
                setattr(self, k, kwargs[k])

    def clone(self):
        """
        Equivalent to sub clone: make a copy of the box object.
        """
        # In Perl, we do
        # my $s = {
        #   coins => [ map {[@$_]} @{ $self->{coins}} ],
        #   droite => $self->{droite}
        # };
        # bless $s;
        new_boite = AMCBox()
        new_boite.coins = [corner[:] for corner in self.coins]  # deep copy each corner
        new_boite.droite = self.droite
        return new_boite

    def def_point_suivant(self, x, y):
        """
        Equivalent to sub def_point_suivant.
        Set the next corner to (x,y).
        """
        self.coins[self.point_actuel] = [x, y]
        self.point_actuel += 1

    def def_droite_MD(self, x, y, dx, dy):
        """
        Equivalent to sub def_droite_MD:
        Define a rectangular box using top-left corner (x,y) 
        and size dx by dy.
        """
        self.coins[0] = [x, y]
        self.coins[1] = [x + dx, y]
        self.coins[2] = [x + dx, y + dy]
        self.coins[3] = [x, y + dy]
        self.droite = 1
        return self

    def def_droite_MN(self, x, y, xp, yp):
        """
        Equivalent to sub def_droite_MN:
        Define a rectangular box using top-left corner (x,y) 
        and bottom-right corner (xp, yp).
        """
        self.coins[0] = [x, y]
        self.coins[1] = [xp, y]
        self.coins[2] = [xp, yp]
        self.coins[3] = [x, yp]
        self.droite = 1
        return self

    def def_droite_xml(self, x):
        """
        Equivalent to sub def_droite_xml:
        Expect x to be a dictionary with keys xmin, ymin, xmax, ymax.
        Then call def_droite_MN.
        """
        self.def_droite_MN(x["xmin"], x["ymin"], x["xmax"], x["ymax"])
        return self

    def def_complete(self, xa, ya, xb, yb, xc, yc, xd, yd):
        """
        Equivalent to sub def_complete:
        Define a full 4-corner box (possibly non-rectangular).
        """
        self.coins[0] = [xa, ya]
        self.coins[1] = [xb, yb]
        self.coins[2] = [xc, yc]
        self.coins[3] = [xd, yd]
        self.droite = 0
        return self

    @staticmethod
    def _un_seul(x):
        """
        Equivalent to sub un_seul in Perl:
        If x is a scalar, return it; if array ref, 
        return the first element, etc. 
        In Python, we check type or do mild guess.
        """
        if x is None:
            return None
        if isinstance(x, (int, float, str)):
            return x
        if isinstance(x, list):
            return x[0] if x else None
        if isinstance(x, dict):
            # Return the value of the first key
            keys = list(x.keys())
            if keys:
                return x[keys[0]]
            return None
        return x  # fallback

    def def_complete_xml(self, x):
        """
        Equivalent to sub def_complete_xml:
        Expect x to be something with x->{coin} or x itself with coin 1..4. 
        Then do def_complete with the corners.
        """
        if "coin" in x:
            x = x["coin"]
        # In Perl, we do:
        #   $self->def_complete(
        #     map { ( un_seul($x->{$_}->{x}), un_seul($x->{$_}->{y}) ) } (1..4)
        #   );
        coords = []
        for i in range(1, 5):
            xi = self._un_seul(x[str(i)]["x"])
            yi = self._un_seul(x[str(i)]["y"])
            coords.extend([xi, yi])
        self.def_complete(*coords)
        return self

    # --------------------------------------------------------------------------
    # Alternative constructors (in Perl: new_MD, new_MN, new_xml, etc.)
    # In Python, we do class methods returning a fresh instance.
    # --------------------------------------------------------------------------
    @classmethod
    def new_MD(cls, x, y, dx, dy):
        """
        Equivalent to sub new_MD in Perl
        """
        instance = cls()
        instance.def_droite_MD(x, y, dx, dy)
        return instance

    @classmethod
    def new_MN(cls, x, y, xp, yp):
        """
        Equivalent to sub new_MN in Perl
        """
        instance = cls()
        instance.def_droite_MN(x, y, xp, yp)
        return instance

    @classmethod
    def new_xml(cls, xmldict):
        """
        Equivalent to sub new_xml in Perl
        """
        instance = cls()
        instance.def_droite_xml(xmldict)
        return instance

    @classmethod
    def new_complete(cls, xa, ya, xb, yb, xc, yc, xd, yd):
        """
        Equivalent to sub new_complete in Perl
        """
        instance = cls()
        instance.def_complete(xa, ya, xb, yb, xc, yc, xd, yd)
        return instance

    @classmethod
    def new_complete_xml(cls, xmldict):
        """
        Equivalent to sub new_complete_xml in Perl
        """
        instance = cls()
        instance.def_complete_xml(xmldict)
        return instance

    # --------------------------------------------------------------------------
    # Output / representation
    # --------------------------------------------------------------------------
    def txt(self):
        """
        Equivalent to sub txt in Perl:
        Return a textual description of the box.
        If 'droite' is True, we assume a rectangle with corner 0,2 as diag.
        """
        if self.droite:
            # (x0,y0)-(x2,y2) dx x dy
            x0, y0 = self.coins[0]
            x2, y2 = self.coins[2]
            dx = x2 - x0
            dy = y2 - y0
            return f"({x0:.2f},{y0:.2f})-({x2:.2f},{y2:.2f}) {dx:.2f} x {dy:.2f}"
        else:
            # (x0,y0) (x1,y1) (x2,y2) (x3,y3)
            c = self.coins
            return ("(%.2f,%.2f) (%.2f,%.2f) (%.2f,%.2f) (%.2f,%.2f)" %
                    (c[0][0], c[0][1],
                     c[1][0], c[1][1],
                     c[2][0], c[2][1],
                     c[3][0], c[3][1]))

    def contour(self):
        """
        Equivalent to sub contour in Perl:
        Return a string with the corners in order + repeat first corner.
        """
        c = self.coins
        return ("%.2f,%.2f %.2f,%.2f %.2f,%.2f %.2f,%.2f %.2f,%.2f" %
                (c[0][0], c[0][1],
                 c[1][0], c[1][1],
                 c[2][0], c[2][1],
                 c[3][0], c[3][1],
                 c[0][0], c[0][1]))

    def diag1(self):
        """
        Equivalent to sub diag1: return a string with corners[0] -> corners[2].
        """
        c = self.coins
        return ("%.2f,%.2f %.2f,%.2f" %
                (c[0][0], c[0][1],
                 c[2][0], c[2][1]))

    def diag2(self):
        """
        Equivalent to sub diag2: return a string with corners[1] -> corners[3].
        """
        c = self.coins
        return ("%.2f,%.2f %.2f,%.2f" %
                (c[1][0], c[1][1],
                 c[3][0], c[3][1]))

    def draw_list(self):
        """
        Equivalent to sub draw_list:
        Return ['-draw', 'polygon x0,y0 x1,y1 x2,y2 x3,y3'] for ImageMagick usage.
        """
        return ["-draw", "polygon " + self.draw_points()]

    def draw_points(self):
        """
        Equivalent to sub draw_points:
        Return "x0,y0 x1,y1 x2,y2 x3,y3".
        """
        c = self.coins
        return ("%.2f,%.2f %.2f,%.2f %.2f,%.2f %.2f,%.2f" %
                (c[0][0], c[0][1],
                 c[1][0], c[1][1],
                 c[2][0], c[2][1],
                 c[3][0], c[3][1]))

    def draw(self):
        """
        Equivalent to sub draw: return the command part in quotes for shell usage.
        """
        # in Perl: return ' ' . join(' ', map { "\"$_\"" } ($self->draw_list)) . ' ';
        # but draw_list returns 2 items, e.g. ["-draw", "polygon ..."]
        dl = self.draw_list()
        # each item in dl should be quoted if we want a single string
        quoted = " ".join(f'"{item}"' for item in dl)
        return f" {quoted} "

    def xml(self, indent=0):
        """
        Equivalent to sub xml in Perl.
        Return a string describing corners in XML with some indentation.
        """
        c = self.coins
        pre = " " * indent
        lines = []
        for i in range(4):
            x_i, y_i = c[i]
            lines.append(f'{pre}<coin id="{i + 1}"><x>{x_i:.4f}</x><y>{y_i:.4f}</y></coin>')
        return "\n".join(lines) + "\n"

    def to_data(self, capture, zoneid, corner_type):
        """
        Equivalent to sub to_data in Perl.
        In AMC, this might call `$capture->set_corner($zoneid, i+1, $type, x, y)`.
        In Python, we just provide a placeholder.
        """
        for i in range(4):
            x, y = self.coins[i]
            # capture.set_corner(zoneid, i+1, corner_type, x, y)
            pass  # placeholder

    def commande_mesure(self, prop):
        """
        Equivalent to sub commande_mesure: 
        Return "mesure prop x0 y0 x1 y1 x2 y2 x3 y3 x4 y4" 
        but the code is slightly ambiguous: in Perl, it references 
        coins[0..4], but we only have 0..3 corners. Possibly a bug 
        or the first corner repeated?
        """
        # The original code loops from 0..4, but we only have 4 corners in [0..3].
        # So let's replicate that logic by repeating the last corner or first corner?
        # The original code: for my $i (0..4) { $c .= " ". join(" ", @{ $self->{coins}->[$i] }) }
        # Possibly it repeated coin[0] at the end. We'll do that.
        coords = self.coins + [self.coins[0]]
        c = f"mesure {prop}"
        for corner in coords:
            c += " " + " ".join(f"{val}" for val in corner)
        return c

    def commande_mesure0(self, prop, shape):
        """
        Equivalent to sub commande_mesure0 in Perl.
        Return "mesure0 prop shape X Y W H" presumably from etendue_xy('xy').
        """
        xy = self.etendue_xy('xy')
        # etendue_xy('xy') -> (xmin, xmax, ymin, ymax)
        # The code suggests we want "xmin, xmax, ymin, ymax" => we want to build 
        # "mesure0 prop shape xmin xmax ymin ymax"? 
        # The original: 
        #   my $c = "mesure0 $prop $shape " . join(' ', $self->etendue_xy('xy'));
        c = f"mesure0 {prop} {shape} {' '.join(str(v) for v in xy)}"
        return c

    def centre(self):
        """
        Equivalent to sub centre in Perl: returns the center (average of corners).
        """
        x_sum = 0.0
        y_sum = 0.0
        for i in range(4):
            x_sum += self.coins[i][0]
            y_sum += self.coins[i][1]
        return (x_sum / 4.0, y_sum / 4.0)

    def centre_projete(self, ux, uy):
        """
        Equivalent to sub centre_projete in Perl:
        Dot product of the center with direction (ux, uy).
        """
        (cx, cy) = self.centre()
        return cx * ux + cy * uy

    # --------------------------------------------------------------------------
    # Sorting a list of boxes by projected center
    # --------------------------------------------------------------------------


def tri_dir(x, y, boites):
    """
    Equivalent to sub tri_dir in Perl: 
    Sort box list by center_projete(x, y).
    """
    boites.sort(key=lambda b: b.centre_projete(x, y))


def extremes(boites):
    """
    Equivalent to sub extremes in Perl:
    Among a list of boxes, return the 4 extreme ones: 
    HG, HD, BD, BG (top-left, top-right, bottom-right, bottom-left).
    This is done by sorting the list in different directions and picking 
    the first item each time. 
    """
    if not boites:
        debug("Warning: Empty list in [extremes] call")
        return []

    # 1) tri_dir(1,1)
    tri_dir(1, 1, boites)
    hg = boites[0]
    # 2) tri_dir(-1,1)
    tri_dir(-1, 1, boites)
    hd = boites[0]
    # 3) tri_dir(-1,-1)
    tri_dir(-1, -1, boites)
    bd = boites[0]
    # 4) tri_dir(1,-1)
    tri_dir(1, -1, boites)
    bg = boites[0]

    return [hg, hd, bd, bg]


def centres_extremes(boites):
    """
    Equivalent to sub centres_extremes in Perl:
    Returns the centers of the extremes in the order [hg, hd, bd, bg].
    """
    ex = extremes(boites)
    return [coord for b in ex for coord in b.centre()]


class AMCBox:
    """
    The AMCBox class continues...
    """

    # continuing from above inside AMCBox for the rest:

    def direction(self, i, j):
        """
        Equivalent to sub direction in Perl:
        angle of corner j relative to corner i.
        """
        dx = self.coins[j][0] - self.coins[i][0]
        dy = self.coins[j][1] - self.coins[i][1]
        return math.atan2(dy, dx)

    def rayon(self):
        """
        Equivalent to sub rayon in Perl: radius of circumscribed circle if the 
        box is a diamond. This is distance from center to corner 0.
        """
        cx, cy = self.centre()
        x0, y0 = self.coins[0]
        return math.sqrt((cx - x0) ** 2 + (cy - y0) ** 2)

    # amc_max, amc_min are at top-level

    def pos_txt(self, ligne):
        """
        Equivalent to sub pos_txt in Perl:
        Return integer coords near the box for labeling text.
        """
        (xmin, ymin, xmax, ymax) = self.etendue_xy('4')
        # in Perl, we do int($xmin - (dx)*1.1, $ymin + (ligne+1)*(dy)/3)
        dx = (xmax - xmin)
        dy = (ymax - ymin)
        px = int(xmin - dx * 1.1)
        py = int(ymin + (ligne + 1) * dy / 3)
        return (px, py)

    def etendue_xy(self, mode, *o):
        """
        Equivalent to sub etendue_xy in Perl:
        Returns bounding box info in various formats, depending on 'mode'.
        - 'xml' => "xmin=\"...\" xmax=\"...\" ymin=\"...\" ymax=\"...\""
        - 'geometry' => "WxH+X+Y" with optional margin and text offset
        - '4' => (xmin, ymin, xmax, ymax)
        - 'xy' => (xmin, xmax, ymin, ymax)
        - 'xmin' => just xmin
        - 'xmax' => just xmax
        - 'ymin' => just ymin
        - 'ymax' => just ymax
        - else => (width, height)
        """
        c0 = self.coins[0]
        xmin = c0[0]
        ymin = c0[1]
        xmax = c0[0]
        ymax = c0[1]

        for i in range(1, 4):
            x = self.coins[i][0]
            y = self.coins[i][1]
            if x > xmax:
                xmax = x
            if x < xmin:
                xmin = x
            if y > ymax:
                ymax = y
            if y < ymin:
                ymin = y

        if mode == 'xml':
            return f'xmin="{xmin:.2f}" xmax="{xmax:.2f}" ymin="{ymin:.2f}" ymax="{ymax:.2f}"'
        elif mode == 'geometry':
            # we expect a margin and maybe a txt arg
            #   in Perl: my($marge,$txt)=@o; ...
            if len(o) >= 1:
                marge = o[0]
            else:
                marge = 0
            # txt was used to call self->pos_txt(-1) if truthy, to adjust coords
            # We'll skip that or replicate partially:
            # if len(o) >= 2 and o[1]:
            #     (xmin, ymin) = self.pos_txt(-1)
            w = (xmax - xmin) + 2 * marge
            h = (ymax - ymin) + 2 * marge
            return f"{w:.2f}x{h:.2f}+{xmin - marge:.2f}+{ymin - marge:.2f}"
        elif mode == '4':
            return (xmin, ymin, xmax, ymax)
        elif mode == 'xy':
            return (xmin, xmax, ymin, ymax)
        elif mode == 'xmin':
            return xmin
        elif mode == 'xmax':
            return xmax
        elif mode == 'ymin':
            return ymin
        elif mode == 'ymax':
            return ymax
        else:
            # default: (width, height)
            return (xmax - xmin, ymax - ymin)

    def coordonnees(self, i, c):
        """
        Equivalent to sub coordonnees in Perl:
        Return x and/or y of corner i, depending on 'c' pattern.
        For example 'xy' => (x_i, y_i), 'x' => x_i, 'y' => y_i, etc.
        """
        x_i, y_i = self.coins[i]
        r = []
        if 'x' in c.lower():
            r.append(x_i)
        if 'y' in c.lower():
            r.append(y_i)
        return r if len(r) != 1 else r[0]

    def diametre(self):
        """
        Equivalent to sub diametre in Perl:
        returns (dx+dy)/2, where dx,dy come from etendue_xy.
        """
        (dx, dy) = self.etendue_xy('')
        return (dx + dy) / 2.0

    def bonne_etendue(self, dmin, dmax):
        """
        Equivalent to sub bonne_etendue in Perl:
        check if bounding box fits between dmin and dmax in both x and y.
        """
        dx, dy = self.etendue_xy('')
        return (dx >= dmin and dx <= dmax and dy >= dmin and dy <= dmax)

    def transforme(self, transf):
        """
        Equivalent to sub transforme in Perl:
        for each corner, apply transf->transforme(x, y). 
        Then set self->droite=0.
        """
        for i in range(4):
            x, y = self.coins[i]
            xp, yp = transf.transforme(x, y)  # see AMC::Calage
            self.coins[i] = [xp, yp]
        self.droite = 0
        return self


# We place the top-level amc_max, amc_min, tri_dir, extremes, centres_extremes in the same file 
# for convenience. They correspond to `@EXPORT_OK = qw(&max &min);` plus the subroutines 
# tri_dir, extremes, centres_extremes in the Perl code.


