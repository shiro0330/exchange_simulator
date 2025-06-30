# Exchange Simulator
import uuid
import heapq
import logging

from decimal import Decimal, ROUND_HALF_UP as rnd

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("Exchange Logger")


class Order:
    """Represents a single order in the exchange."""
    _symbol_seq = {}  # class-level dic to track seq per symbol

    def __init__(self, symbol: str, side: str, price: float, quantity: int, order_id: int = None):
        symbol_upper = symbol.upper()
        if order_id is not None:
            self.order_id = order_id
        else:
            # Increment sequence for this symbol
            seq = Order._symbol_seq.get(symbol_upper, 1)
            self.order_id = seq
            Order._symbol_seq[symbol_upper] = seq + 1
        self.symbol = symbol_upper
        self.side = side.upper()  # 'BUY' or 'SELL'
        self.price = Decimal(price).quantize(Decimal("0.01"), rounding=rnd)
        self.quantity = int(quantity)
        self.original_quantity = int(quantity)  # Track original quantity

    def execute(self, exec_quantity: int) -> int:
        """Execute a portion of the order and return the executed quantity.
        
        Args:
            exec_quantity: The quantity to execute
            
        Returns:
            The actual executed quantity (may be less than requested if insufficient quantity)
            
        Raises:
            ValueError: If exec_quantity is negative or zero
        """
        if exec_quantity <= 0:
            raise ValueError("Execution quantity must be positive")
        
        actual_exec_qty = min(exec_quantity, self.quantity)
        self.quantity -= actual_exec_qty
        return actual_exec_qty
    
    def is_filled(self) -> bool:
        """Check if the order is completely filled."""
        return self.quantity == 0
        

    def __repr__(self):
        return (f"Order(order_id={self.order_id}, symbol='{self.symbol}', side='{self.side}', "
                f"price={self.price}, quantity={self.quantity})")


class OrderBook:
    """Order book for a single symbol"""
    _registry = []  # Class-level list to track all OrderBook instances

    def __init__(self, symbol: str = None):
        self.symbol = symbol or uuid.uuid4().hex[:3].upper() # Create randomly if not given
        self.bids = []  # max-heap: (-price, order_id, order) i.e. larger price is better
        self.offers = []  # min-heap: (price, order_id, order) i.e. smaller price is better
        self.trades = []  # List of executed trades: dicts with info
        self.positions = {}  # symbol -> net position (int)
        OrderBook._registry.append(self)

    def _record_trade(self, buy_id, sell_id, price, quantity, active_side=None):
        trade = {
            'symbol': self.symbol,
            'buy_order_id': buy_id,
            'sell_order_id': sell_id,
            'price': price,
            'quantity': quantity
        }
        self.trades.append(trade)
        # Update position for symbol: + for buy, - for sell
        if active_side == 'BUY':
            self.positions[self.symbol] = self.positions.get(self.symbol, 0) + quantity
        elif active_side == 'SELL':
            self.positions[self.symbol] = self.positions.get(self.symbol, 0) - quantity
        else:
            # fallback: do nothing
            pass

    def _match_order(self, order, heap, price_getter, price_cmp, trade_log_fmt, heap_pop, price_sign=1):
        while heap and order.quantity > 0:
            best_price_raw, best_id, best_order = heap[0]
            best_price = price_sign * best_price_raw
            if price_cmp(order.price, best_price):
                trade_qty = min(order.quantity, best_order.quantity)
                LOGGER.info(trade_log_fmt.format(trade_qty=trade_qty, price=best_price, buy_id=order.order_id, sell_id=best_order.order_id))
                
                # Use the new execute method instead of direct quantity manipulation
                actual_trade_qty = order.execute(trade_qty)
                best_order.execute(actual_trade_qty)
                
                self._record_trade(
                    buy_id=order.order_id if order.side == 'BUY' else best_order.order_id,
                    sell_id=best_order.order_id if order.side == 'BUY' else order.order_id,
                    price=best_price,
                    quantity=actual_trade_qty,
                    active_side=order.side
                )
                
                if best_order.is_filled():
                    heapq.heappop(heap)
                else:
                    break  # Partial fill, stop matching
            else:
                break  # No match (further)
        return order.is_filled()  # True if fully matched

    def add_order(self, order: Order) -> None:
        if order.symbol != self.symbol:
            raise ValueError(f"Order symbol '{order.symbol}' does not match OrderBook symbol '{self.symbol}'")
        LOGGER.info(f'Adding Order: {order}')

        if order.side == 'BUY':
            fully_matched = self._match_order(
                order,
                self.offers,
                lambda x: x[0],
                lambda buy, offer: buy >= offer,
                "Executed: BUY {trade_qty} @ {price} between Order {buy_id} and {sell_id}",
                heapq.heappop,
                price_sign=1
            )
            if not fully_matched:
                heapq.heappush(self.bids, (-order.price, order.order_id, order))
        elif order.side == 'SELL':
            fully_matched = self._match_order(
                order,
                self.bids,
                lambda x: -x[0],
                lambda sell, bid: sell <= bid,
                "Executed: SELL {trade_qty} @ {price} between Order# {sell_id} and {buy_id}",
                heapq.heappop,
                price_sign=-1
            )
            if not fully_matched:
                heapq.heappush(self.offers, (order.price, order.order_id, order))
        else:
            raise Exception(f"Unknown order side: {order.side}")

    def display_book(self) -> None:
        total_orders = len(self.bids) + len(self.offers)
        LOGGER.info(f'Display Order Book: {self.symbol} | Total Orders: {total_orders}')
        print("\n" + "#"*34)
        print("#          BUY ORDERS            #")
        print("#"*34)
        for _, _, order in sorted(self.bids, reverse=True):
            print(order)
        print("#"*34)
        print("#          SELL ORDERS           #")
        print("#"*34)
        for _, _, order in sorted(self.offers):
            print(order)
        print()

    def show_trades(self) -> None:
        print("\n########## EXECUTED TRADES ##########")
        if not self.trades:
            print("No trades executed.")
        else:
            for t in self.trades:
                print(f"Trade: {t['symbol']} | BUY Order #{t['buy_order_id']} <-> SELL Order #{t['sell_order_id']} | Qty: {t['quantity']} @ {t['price']}")
        print("#"*36)

    def show_position(self) -> None:
        print("\n########## POSITION ##########")
        for symbol, qty in self.positions.items():
            print(f"{symbol}: {qty}")
        print("#"*24)

    @classmethod
    def show_all_trades(cls):
        print("\n########## ALL EXECUTED TRADES ##########")
        for book in cls._registry:
            print(f"[OrderBook: {book.symbol}]")
            if not book.trades:
                print("  No trades executed.")
            else:
                for t in book.trades:
                    print(f"  Trade: {t['symbol']} | BUY Order #{t['buy_order_id']} <-> SELL Order #{t['sell_order_id']} | Qty: {t['quantity']} @ {t['price']}")
        print("#"*36)

    @classmethod
    def show_all_positions(cls):
        print("\n########## ALL POSITIONS ##########")
        for book in cls._registry:
            for symbol, qty in book.positions.items():
                print(f"[OrderBook: {book.symbol}] {symbol}: {qty}")
        print("#"*24)

def send_order(order_book, order_list):
    """Send a list of orders to the given order book using add_order."""
    for order in order_list:
        order_book.add_order(order)


def main():
    # Create new market base for TESLA
    tesla_book = OrderBook('TESLA')
    o1 = Order(symbol='TESLA', side='BUY', price=100.00, quantity=35)
    o2 = Order(symbol='TESLA', side='SELL', price=102.00, quantity=10)
    o3 = Order(symbol='TESLA', side='SELL', price=101.00, quantity=30)
    send_order(tesla_book,[o1,o2,o3])
    tesla_book.display_book()

    # Enter new orders to cross
    o4 = Order(symbol='TESLA', side='BUY', price=103.00, quantity=10) # take partially (10) on o3
    o5 = Order(symbol='TESLA', side='BUY', price=103.00, quantity=10) # take again partially (10) on o3
    o6 = Order(symbol='TESLA', side='BUY', price=103.00, quantity=30) # take fully (10) on o3, then on o2(10), the rest (10) remains
    o7 = Order(symbol='TESLA', side='SELL', price=100.00, quantity=60) # take
    send_order(tesla_book, [o4,o5,o6,o7])


     # Create new market base for TOYOTA
    toyota_book = OrderBook('TOYOTA')
    oo1 = Order(symbol='TOYOTA', side='BUY', price=100.00, quantity=10)
    oo2 = Order(symbol='TOYOTA', side='SELL', price=101.00, quantity=10)
    oo3 = Order(symbol='TOYOTA', side='BUY', price=100.00, quantity=10)
    send_order(toyota_book, [oo1,oo2,oo3])
    toyota_book.display_book()

    # Enter new orders to cross
    oo4 = Order(symbol='TOYOTA', side='SELL', price=100.00, quantity=20) # first take on oo1 then on oo3
    send_order(toyota_book, [oo4])


    # Create new market base for BYD
    byd_book = OrderBook('BYD')
    ooo1 = Order(symbol='BYD', side='BUY', price=100.00, quantity=10)


    # Summary of executed trades and positions
    tesla_book.show_trades()
    tesla_book.show_position()
    toyota_book.show_trades()
    toyota_book.show_position()
    OrderBook.show_all_trades()
    OrderBook.show_all_positions()


if __name__ == "__main__":
    main()




