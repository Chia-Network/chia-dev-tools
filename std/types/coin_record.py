from dataclasses import dataclass

from lib.std.types.coin import Coin
from lib.std.types.sized_bytes import bytes32
from lib.std.types.ints import uint32, uint64
from lib.std.types.streamable import Streamable, streamable


@dataclass(frozen=True)
@streamable
class CoinRecord(Streamable):
    """
    These are values that correspond to a CoinName that are used
    in keeping track of the unspent database.
    """

    coin: Coin
    confirmed_block_index: uint32
    spent_block_index: uint32
    spent: bool
    coinbase: bool
    timestamp: uint64

    @property
    def name(self) -> bytes32:
        return self.coin.name()
