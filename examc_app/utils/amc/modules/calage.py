import math

from examc_app.utils.amc.modules.basic import debug


class AMCCalage:
    """
    Python translation of the Perl package AMC::Calage.
    """

    # Equivalent constants
    M_PI = math.atan2(1, 1) * 4
    HUGE = 32000

    def __init__(self, **kwargs):
        """
        Translated from 'sub new' in Perl.
        Sets default values, then calls self.set(**kwargs).
        Finally, it calls identity() and clear_min_max().
        """
        # Defaults
        self.type = 'lineaire'
        self.log = True
        self.t_a = 1.0
        self.t_b = 0.0
        self.t_c = 0.0
        self.t_d = 1.0
        self.t_e = 0.0
        self.t_f = 0.0
        self.MSE = 0.0

        self.t_x_min = 0
        self.t_y_min = 0
        self.t_x_max = 0
        self.t_y_max = 0

        # Apply any user overrides
        self.set(**kwargs)

        # Equivalent to $self->identity(); in new()
        self.identity()
        # Equivalent to $self->clear_min_max();
        self.clear_min_max()

    def set(self, **kwargs):
        """
        Translated from 'sub set' in Perl:
        Updates object attributes if they exist in self.
        """
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def mse(self):
        """
        Translated from 'sub mse' in Perl.
        Returns the current MSE value.
        """
        return self.MSE

    def identity(self):
        """
        Translated from 'sub identity' in Perl.
        Resets transformation to the identity transform.
        """
        self.type = 'lineaire'
        self.t_a = 1.0
        self.t_b = 0.0
        self.t_c = 0.0
        self.t_d = 1.0
        self.t_e = 0.0
        self.t_f = 0.0
        self.MSE = 0.0

    @staticmethod
    def moyenne(arr):
        """
        Translated from 'sub moyenne' in Perl.
        Returns the mean of the elements in arr.
        """
        if not arr:
            return 0.0
        return sum(arr) / len(arr)

    @staticmethod
    def crochet(a, b):
        """
        Translated from 'sub crochet' in Perl.
        Computation of the 'cross' measure used in the code.
        """
        ma = AMCCalage.moyenne(a)
        mb = AMCCalage.moyenne(b)
        s = 0.0
        for i in range(len(a)):
            s += (a[i] - ma) * (b[i] - mb)
        return s / len(a) if len(a) > 0 else 0.0

    @staticmethod
    def resoud_22(a, b, c, d, e, f):
        """
        Translated from 'sub resoud_22' in Perl.
        Solves a 2x2 system:
            a*x + b*y = e
            c*x + d*y = f
        Returns (x, y).
        """
        delta = a * d - b * c
        x = (d * e - b * f) / delta
        y = (-c * e + a * f) / delta
        return x, y

    def clear_min_max(self):
        """
        Translated from 'sub clear_min_max' in Perl.
        Resets the bounding box values.
        """
        self.t_x_min = self.HUGE
        self.t_y_min = self.HUGE
        self.t_x_max = 0
        self.t_y_max = 0

    def transforme(self, x, y, nominmax=False):
        """
        Translated from 'sub transforme' in Perl.
        Applies the linear (or Helmert) transformation to (x,y).
        Updates the bounding box unless nominmax=True.
        """
        if self.type.lower().startswith('h') or self.type.lower().startswith('l'):
            xp = self.t_a * x + self.t_b * y + self.t_e
            yp = self.t_c * x + self.t_d * y + self.t_f
        else:
            # Default to identity if unknown type, or raise an error
            xp, yp = x, y

        if not nominmax:
            if xp < self.t_x_min:
                self.t_x_min = xp
            if yp < self.t_y_min:
                self.t_y_min = yp
            if xp > self.t_x_max:
                self.t_x_max = xp
            if yp > self.t_y_max:
                self.t_y_max = yp

        return xp, yp

    def calage(self, cx, cy, cxp, cyp):
        """
        Translated from 'sub calage' in Perl.
        Adjusts the transformation parameters to best match the
        (cx,cy) points to (cxp,cyp) points via either Helmert or
        linear approach.
        """
        # We check the transform type
        if self.type.lower().startswith('h'):
            # HELMERT
            theta = math.atan2(
                self.crochet(cx, cyp) - self.crochet(cxp, cy),
                self.crochet(cx, cxp) + self.crochet(cy, cyp)
            )
            debug(f"theta = {theta * 180.0 / self.M_PI:.3f}\n")

            den = self.crochet(cx, cx) + self.crochet(cy, cy)
            if abs(math.cos(theta)) > abs(math.sin(theta)):
                alpha = (self.crochet(cx, cxp) + self.crochet(cy, cyp)) / (den * math.cos(theta))
            else:
                alpha = (self.crochet(cx, cyp) - self.crochet(cxp, cy)) / (den * math.sin(theta))

            # If alpha < 0, adjust alpha and theta
            if alpha < 0:
                alpha = abs(alpha)
                if theta > 0:
                    theta -= self.M_PI
                else:
                    theta += self.M_PI

            self.t_e = (
                    self.moyenne(cxp)
                    - alpha * (
                            self.moyenne(cx) * math.cos(theta)
                            - self.moyenne(cy) * math.sin(theta)
                    )
            )
            self.t_f = (
                    self.moyenne(cyp)
                    - alpha * (
                            self.moyenne(cx) * math.sin(theta)
                            + self.moyenne(cy) * math.cos(theta)
                    )
            )

            debug(f"alpha = {alpha}\n")

            self.t_a = alpha * math.cos(theta)
            self.t_b = -alpha * math.sin(theta)
            self.t_c = alpha * math.sin(theta)
            self.t_d = alpha * math.cos(theta)

        elif self.type.lower().startswith('l'):
            # LINEAR
            sxx = self.crochet(cx, cx)
            sxy = self.crochet(cx, cy)
            syy = self.crochet(cy, cy)

            sxxp = self.crochet(cx, cxp)
            syxp = self.crochet(cy, cxp)
            sxyp = self.crochet(cx, cyp)
            syyp = self.crochet(cy, cyp)

            self.t_a, self.t_b = self.resoud_22(sxx, sxy, sxy, syy, sxxp, syxp)
            self.t_e = self.moyenne(cxp) - (
                    self.t_a * self.moyenne(cx) + self.t_b * self.moyenne(cy)
            )

            self.t_c, self.t_d = self.resoud_22(sxx, sxy, sxy, syy, sxyp, syyp)
            self.t_f = self.moyenne(cyp) - (
                    self.t_c * self.moyenne(cx) + self.t_d * self.moyenne(cy)
            )

        else:
            debug(f"ERR: invalid type: {self.type}\n")

        if self.log and (self.type.lower().startswith('h') or self.type.lower().startswith('l')):
            debug("Linear transform:\n")
            debug(
                f" {self.t_a:7.3f} {self.t_b:7.3f}     {self.t_e:10.3f}\n"
                f" {self.t_c:7.3f} {self.t_d:7.3f}     {self.t_f:10.3f}\n"
            )

        # Compute MSE
        sd = 0.0
        n = len(cx)
        for i in range(n):
            x, y = self.transforme(cx[i], cy[i], nominmax=True)
            dx = x - cxp[i]
            dy = y - cyp[i]
            sd += dx * dx + dy * dy

        self.MSE = math.sqrt(sd / n) if n > 0 else 0.0

        debug(f"MSE = {self.MSE:.3f}\n")
        if self.log:
            print(f"Adjust: MSE = {self.MSE:.3f}")

        return self.MSE

    def params(self):
        """
        Translated from 'sub params' in Perl.
        Returns (t_a, t_b, t_c, t_d, t_e, t_f, MSE).
        """
        return (self.t_a, self.t_b, self.t_c, self.t_d, self.t_e, self.t_f, self.MSE)

    def xml(self, indent=0):
        """
        Translated from 'sub xml' in Perl.
        Returns an XML representation of the transform parameters.
        """
        pre = " " * indent
        r = f'{pre}<transformation type="{self.type}" mse="{self.MSE}">\n'
        r += f'{pre}  <parametres>\n'
        if self.type.lower().startswith('h') or self.type.lower().startswith('l'):
            r += f'{pre}      <a>{self.t_a}</a>\n'
            r += f'{pre}      <b>{self.t_b}</b>\n'
            r += f'{pre}      <c>{self.t_c}</c>\n'
            r += f'{pre}      <d>{self.t_d}</d>\n'
            r += f'{pre}      <e>{self.t_e}</e>\n'
            r += f'{pre}      <f>{self.t_f}</f>\n'
        r += f'{pre}  </parametres>\n'
        r += f'{pre}</transformation>\n'
        return r


# Example usage:
if __name__ == "__main__":
    # Create an instance with defaults
    cal = AMCCalage(type='lineaire', log=True)

    # Suppose we have some corresponding points
    cx = [1.0, 2.0, 3.0]
    cy = [4.0, 5.0, 6.0]
    cxp = [1.1, 2.1, 3.1]
    cyp = [3.9, 5.2, 6.05]

    # Perform the 'calage' (adjustment)
    mse_value = cal.calage(cx, cy, cxp, cyp)

    # Print MSE and parameters
    print("MSE:", mse_value)
    print("Parameters:", cal.params())

    # Print XML
    print(cal.xml(indent=2))
