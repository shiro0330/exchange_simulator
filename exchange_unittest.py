import unittest
import exchange
import logging
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

class TestExchange(unittest.TestCase):
    def setUp(self):
        # Clear OrderBook registry and Order sequence for clean tests
        exchange.OrderBook._registry.clear()
        exchange.Order._symbol_seq.clear()

    def test_order(self):
        LOGGER.info('Creating Order')
        symbol = 'TESLA'
        side  = 'BUY'
        price = 105.25
        quantity = 25

        order = exchange.Order(symbol, side, price, quantity)
        self.assertEqual(order.symbol, symbol)
        self.assertEqual(order.side, side)
        self.assertEqual(order.price, exchange.Decimal(str(price)).quantize(exchange.Decimal("0.01"), rounding=exchange.rnd))
        self.assertEqual(order.quantity, quantity)
        self.assertIsNotNone(order.order_id)

    def test_orderbook_add_and_match(self):
        book = exchange.OrderBook('TESLA')
        b1 = exchange.Order('TESLA', 'BUY', 100.00, 10)
        s1 = exchange.Order('TESLA', 'SELL', 99.00, 10)
        exchange.send_order(book, [b1, s1])
        # Should match and not remain in book
        self.assertEqual(len(book.bids), 0)
        self.assertEqual(len(book.offers), 0)
        self.assertEqual(len(book.trades), 1)
        self.assertEqual(book.trades[0]['quantity'], 10)
        self.assertEqual(book.positions['TESLA'], -10)

    def test_short_position(self):
        book = exchange.OrderBook('TESLA')
        s1 = exchange.Order('TESLA', 'SELL', 100.00, 10)
        b1 = exchange.Order('TESLA', 'BUY', 101.00, 5)
        b2 = exchange.Order('TESLA', 'BUY', 101.00, 5)
        exchange.send_order(book, [s1, b1, b2])
        self.assertEqual(book.positions['TESLA'], 10)
        # Now add another sell to go short
        s2 = exchange.Order('TESLA', 'SELL', 99.00, 5)
        exchange.send_order(book, [s2])
        self.assertEqual(book.positions['TESLA'], 10)

    def test_all_books_summary(self):
        tesla_book = exchange.OrderBook('TESLA')
        toyota_book = exchange.OrderBook('TOYOTA')
        t1 = exchange.Order('TESLA', 'BUY', 100, 10)
        t2 = exchange.Order('TESLA', 'SELL', 100, 10)
        y1 = exchange.Order('TOYOTA', 'BUY', 100, 5)
        y2 = exchange.Order('TOYOTA', 'SELL', 100, 5)
        exchange.send_order(tesla_book, [t1, t2])
        exchange.send_order(toyota_book, [y1, y2])
        # Should not raise and should print summary
        exchange.OrderBook.show_all_trades()
        exchange.OrderBook.show_all_positions()

if __name__ == "__main__":
    unittest.main(verbosity=2)

