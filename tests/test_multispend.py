from lib.std.test import TestGroup

class CoinTests(TestGroup):
    def do_multi_spend(self,use_amount):
        alice = self.network.make_wallet('alice')
        bob = self.network.make_wallet('bob')

        # Farm for alice
        self.network.farm_block(farmer=alice)
        self.network.farm_block(farmer=alice)

        alice_start_balance = alice.balance()
        bob_start_balance = bob.balance()

        # Give 'amount' chia (for which we won't have a single coin big enough)
        # to bob.  This will only work if we're combining coins.
        result = alice.give_chia(bob, use_amount)

        assert result

        assert bob.balance() == bob_start_balance + use_amount
        assert alice.balance() == alice_start_balance - use_amount

    def test_1_chia(self):
        self.do_multi_spend(1 * self.coin_multiple)

    def test_2_chia(self):
        self.do_multi_spend(2 * self.coin_multiple)

    def test_3_chia(self):
        self.do_multi_spend(3 * self.coin_multiple)

    def test_4_chia(self):
        self.do_multi_spend(4 * self.coin_multiple)
