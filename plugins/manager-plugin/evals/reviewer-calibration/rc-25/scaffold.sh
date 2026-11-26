#!/usr/bin/env bash
# The workspace of rc-25: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'shop' 'Pricing module' 'The price rules move from `orders.py` to '\
'a new `pricing.py` under shorter names (`calc_subtotal` becomes `subtotal`, '\
'and so on), so `orders.py` keeps only the order itself.' \
  '`orders.py`, `pricing.py`, `tests/`' \
  'every price rule gives the same result as before the move; `orders.py` '\
'holds no price rule; the tests use the new names'
cat > 'orders.py' <<'EOF'
"""Orders of the shop: their lines, coupons, prices and totals."""

VAT_RATE = 0.19
HOME_COUNTRY = "DE"
FREE_SHIPPING_FROM = 50.0
SHIPPING_HOME = 4.90
SHIPPING_ABROAD = 12.50
COUPONS = {"WELCOME10": 0.10, "SPRING15": 0.15}


def new_order(customer, country):
    """An empty order of `customer`, shipped to `country` (a two-letter code)."""
    return {"customer": customer, "country": country.upper(), "lines": [], "coupon": None}


def add_line(order, sku, price, quantity=1):
    """Adds `quantity` of `sku` at the unit `price`; a second line of the same sku adds up."""
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    for line in order["lines"]:
        if line["sku"] == sku:
            line["quantity"] += quantity
            return
    order["lines"].append({"sku": sku, "price": price, "quantity": quantity})


def remove_line(order, sku):
    """Removes the line of `sku`; KeyError when the order has none."""
    for index, line in enumerate(order["lines"]):
        if line["sku"] == sku:
            del order["lines"][index]
            return
    raise KeyError(sku)


def apply_coupon(order, code):
    """Sets the order's coupon; ValueError for an unknown code."""
    code = code.strip().upper()
    if code not in COUPONS:
        raise ValueError("unknown coupon: %s" % code)
    order["coupon"] = code


def calc_subtotal(order):
    """The sum of the order's lines, before discount, shipping and VAT."""
    return round(sum(line["price"] * line["quantity"] for line in order["lines"]), 2)


def calc_discount(order):
    """The coupon's discount on the subtotal, 0 without a coupon."""
    rate = COUPONS.get(order["coupon"], 0.0)
    return round(calc_subtotal(order) * rate, 2)


def calc_shipping(order):
    """No lines: nothing. Shipped at home from FREE_SHIPPING_FROM after the discount: free.
    Otherwise the home or the abroad rate."""
    if not order["lines"]:
        return 0.0
    net = calc_subtotal(order) - calc_discount(order)
    if net >= FREE_SHIPPING_FROM and order["country"] == HOME_COUNTRY:
        return 0.0
    if order["country"] == HOME_COUNTRY:
        return SHIPPING_HOME
    return SHIPPING_ABROAD


def calc_vat(order):
    """The VAT on the discounted subtotal and the shipping."""
    taxed = calc_subtotal(order) - calc_discount(order) + calc_shipping(order)
    return round(taxed * VAT_RATE, 2)


def calc_total(order):
    """What the customer pays."""
    return round(calc_subtotal(order) - calc_discount(order) + calc_shipping(order)
                 + calc_vat(order), 2)


def calc_points(order):
    """The loyalty points of the order: one per whole euro of the subtotal, none with a
    coupon."""
    if order["coupon"]:
        return 0
    return int(calc_subtotal(order))


def summary_lines(order):
    """The order's summary as text lines, one per line item and one per amount."""
    lines = ["%dx %s  %.2f" % (line["quantity"], line["sku"], line["price"] * line["quantity"])
             for line in order["lines"]]
    lines.append("Subtotal  %.2f" % calc_subtotal(order))
    if order["coupon"]:
        lines.append("Coupon %s  -%.2f" % (order["coupon"], calc_discount(order)))
    lines.append("Shipping  %.2f" % calc_shipping(order))
    lines.append("VAT  %.2f" % calc_vat(order))
    lines.append("Total  %.2f" % calc_total(order))
    lines.append("Points  %d" % calc_points(order))
    return lines
EOF
cat > 'tests/test_orders.py' <<'EOF'
import unittest

from orders import (add_line, apply_coupon, calc_discount, calc_points, calc_shipping,
                    calc_subtotal, calc_total, calc_vat, new_order, remove_line, summary_lines)


def order(country="DE", *lines):
    made = new_order("ada", country)
    for sku, price, quantity in lines:
        add_line(made, sku, price, quantity)
    return made


class LinesTest(unittest.TestCase):
    def test_lines(self):
        made = order("de", ("pen", 2.0, 1), ("pen", 2.0, 2), ("ink", 5.0, 1))
        self.assertEqual(made["country"], "DE")
        self.assertEqual([(l["sku"], l["quantity"]) for l in made["lines"]],
                         [("pen", 3), ("ink", 1)])
        remove_line(made, "pen")
        self.assertRaises(KeyError, remove_line, made, "pen")
        self.assertRaises(ValueError, add_line, made, "pen", 2.0, 0)

    def test_coupon(self):
        made = order("DE", ("pen", 10.0, 2))
        apply_coupon(made, " welcome10 ")
        self.assertEqual(calc_discount(made), 2.0)
        self.assertRaises(ValueError, apply_coupon, made, "NOPE")


class PricesTest(unittest.TestCase):
    def test_home(self):
        small = order("DE", ("pen", 10.0, 2))
        self.assertEqual((calc_subtotal(small), calc_shipping(small)), (20.0, 4.90))
        self.assertEqual((calc_vat(small), calc_total(small)), (4.73, 29.63))
        large = order("DE", ("pen", 10.0, 6))
        self.assertEqual((calc_shipping(large), calc_total(large)), (0.0, 71.4))

    def test_abroad_and_empty(self):
        self.assertEqual(calc_shipping(order("FR", ("pen", 10.0, 2))), 12.50)
        self.assertEqual(calc_total(order("FR")), 0.0)

    def test_the_discount_counts_for_free_shipping(self):
        made = order("DE", ("pen", 10.0, 5))
        apply_coupon(made, "SPRING15")
        self.assertEqual(calc_shipping(made), 4.90)

    def test_points(self):
        made = order("DE", ("pen", 10.0, 2), ("ink", 0.99, 1))
        self.assertEqual(calc_points(made), 20)
        apply_coupon(made, "WELCOME10")
        self.assertEqual(calc_points(made), 0)

    def test_summary(self):
        made = order("DE", ("pen", 10.0, 2))
        self.assertEqual(summary_lines(made), ["2x pen  20.00", "Subtotal  20.00",
                                               "Shipping  4.90", "VAT  4.73", "Total  29.63",
                                               "Points  20"])
EOF
rc_commit 00 'Base: shop'
rc_branch
cat > 'pricing.py' <<'EOF'
"""The price rules of an order: subtotal, discount, shipping, VAT and total."""

VAT_RATE = 0.19
HOME_COUNTRY = "DE"
FREE_SHIPPING_FROM = 50.0
SHIPPING_HOME = 4.90
SHIPPING_ABROAD = 12.50
COUPONS = {"WELCOME10": 0.10, "SPRING15": 0.15}


def subtotal(order):
    """The sum of the order's lines, before discount, shipping and VAT."""
    return round(sum(line["price"] * line["quantity"] for line in order["lines"]), 2)


def discount(order):
    """The coupon's discount on the subtotal, 0 without a coupon."""
    rate = COUPONS.get(order["coupon"], 0.0)
    return round(subtotal(order) * rate, 2)


def shipping(order):
    """No lines: nothing. Shipped at home from FREE_SHIPPING_FROM after the discount: free.
    Otherwise the home or the abroad rate."""
    if not order["lines"]:
        return 0.0
    net = subtotal(order) - discount(order)
    if net >= FREE_SHIPPING_FROM:
        return 0.0
    if order["country"] == HOME_COUNTRY:
        return SHIPPING_HOME
    return SHIPPING_ABROAD


def vat(order):
    """The VAT on the discounted subtotal and the shipping."""
    taxed = subtotal(order) - discount(order) + shipping(order)
    return round(taxed * VAT_RATE, 2)


def total(order):
    """What the customer pays."""
    return round(subtotal(order) - discount(order) + shipping(order) + vat(order), 2)


def points(order):
    """The loyalty points of the order: one per whole euro of the subtotal, none with a
    coupon."""
    if order["coupon"]:
        return 0
    return int(subtotal(order))
EOF
cat > 'orders.py' <<'EOF'
"""Orders of the shop: their lines, coupons and summary; the prices are in pricing.py."""
import pricing


def new_order(customer, country):
    """An empty order of `customer`, shipped to `country` (a two-letter code)."""
    return {"customer": customer, "country": country.upper(), "lines": [], "coupon": None}


def add_line(order, sku, price, quantity=1):
    """Adds `quantity` of `sku` at the unit `price`; a second line of the same sku adds up."""
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    for line in order["lines"]:
        if line["sku"] == sku:
            line["quantity"] += quantity
            return
    order["lines"].append({"sku": sku, "price": price, "quantity": quantity})


def remove_line(order, sku):
    """Removes the line of `sku`; KeyError when the order has none."""
    for index, line in enumerate(order["lines"]):
        if line["sku"] == sku:
            del order["lines"][index]
            return
    raise KeyError(sku)


def apply_coupon(order, code):
    """Sets the order's coupon; ValueError for an unknown code."""
    code = code.strip().upper()
    if code not in pricing.COUPONS:
        raise ValueError("unknown coupon: %s" % code)
    order["coupon"] = code


def summary_lines(order):
    """The order's summary as text lines, one per line item and one per amount."""
    lines = ["%dx %s  %.2f" % (line["quantity"], line["sku"], line["price"] * line["quantity"])
             for line in order["lines"]]
    lines.append("Subtotal  %.2f" % pricing.subtotal(order))
    if order["coupon"]:
        lines.append("Coupon %s  -%.2f" % (order["coupon"], pricing.discount(order)))
    lines.append("Shipping  %.2f" % pricing.shipping(order))
    lines.append("VAT  %.2f" % pricing.vat(order))
    lines.append("Total  %.2f" % pricing.total(order))
    lines.append("Points  %d" % pricing.points(order))
    return lines
EOF
cat > 'tests/test_orders.py' <<'EOF'
import unittest

from orders import add_line, apply_coupon, new_order, remove_line, summary_lines


def order(country="DE", *lines):
    made = new_order("ada", country)
    for sku, price, quantity in lines:
        add_line(made, sku, price, quantity)
    return made


class LinesTest(unittest.TestCase):
    def test_lines(self):
        made = order("de", ("pen", 2.0, 1), ("pen", 2.0, 2), ("ink", 5.0, 1))
        self.assertEqual(made["country"], "DE")
        self.assertEqual([(l["sku"], l["quantity"]) for l in made["lines"]],
                         [("pen", 3), ("ink", 1)])
        remove_line(made, "pen")
        self.assertRaises(KeyError, remove_line, made, "pen")
        self.assertRaises(ValueError, add_line, made, "pen", 2.0, 0)

    def test_coupon(self):
        made = order("DE", ("pen", 10.0, 2))
        apply_coupon(made, " welcome10 ")
        self.assertEqual(made["coupon"], "WELCOME10")
        self.assertRaises(ValueError, apply_coupon, made, "NOPE")

    def test_summary(self):
        made = order("DE", ("pen", 10.0, 2))
        self.assertEqual(summary_lines(made), ["2x pen  20.00", "Subtotal  20.00",
                                               "Shipping  4.90", "VAT  4.73", "Total  29.63",
                                               "Points  20"])
EOF
cat > 'tests/test_pricing.py' <<'EOF'
import unittest

from orders import add_line, apply_coupon, new_order
from pricing import discount, points, shipping, subtotal, total, vat


def order(country="DE", *lines):
    made = new_order("ada", country)
    for sku, price, quantity in lines:
        add_line(made, sku, price, quantity)
    return made


class PricesTest(unittest.TestCase):
    def test_home(self):
        small = order("DE", ("pen", 10.0, 2))
        self.assertEqual((subtotal(small), shipping(small)), (20.0, 4.90))
        self.assertEqual((vat(small), total(small)), (4.73, 29.63))
        large = order("DE", ("pen", 10.0, 6))
        self.assertEqual((shipping(large), total(large)), (0.0, 71.4))

    def test_abroad_and_empty(self):
        self.assertEqual(shipping(order("FR", ("pen", 10.0, 2))), 12.50)
        self.assertEqual(total(order("FR")), 0.0)

    def test_discount(self):
        made = order("DE", ("pen", 10.0, 2))
        apply_coupon(made, "WELCOME10")
        self.assertEqual(discount(made), 2.0)

    def test_the_discount_counts_for_free_shipping(self):
        made = order("DE", ("pen", 10.0, 5))
        apply_coupon(made, "SPRING15")
        self.assertEqual(shipping(made), 4.90)

    def test_points(self):
        made = order("DE", ("pen", 10.0, 2), ("ink", 0.99, 1))
        self.assertEqual(points(made), 20)
        apply_coupon(made, "WELCOME10")
        self.assertEqual(points(made), 0)
EOF
rc_mark_done
rc_commit 10 'P1: Pricing module'
rc_publish
