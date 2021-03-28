import dataclasses
import collections
from typing import Dict, List, Optional, Set, Tuple

from blspy import G1Element, AugSchemeMPL

from lib.std.types.errors import Err
from lib.std.types.ints import uint64, uint32
from lib.std.types.sized_bytes import bytes32
from lib.std.types.spend_bundle import SpendBundle
from lib.std.types.coin import Coin
from lib.std.types.coin_record import CoinRecord
from lib.std.types.mempool_inclusion_status import MempoolInclusionStatus
from lib.std.types.streamable import dataclass_from_dict, recurse_jsonify
from lib.std.types.consensus_constants import ConsensusConstants
from lib.std.types.name_puzzle_condition import additions_for_npc
from lib.std.types.condition_opcodes import ConditionOpcode
from lib.std.types.condition_var_pair import ConditionVarPair
from lib.std.sim.bundle_tools import best_solution_program
from lib.std.sim.cost_calculator import CostResult, calculate_cost_of_program
from lib.std.sim.mempool_check_conditions import mempool_check_conditions_dict
from lib.std.sim.default_constants import DEFAULT_CONSTANTS
from lib.std.util.condition_tools import pkm_pairs_for_conditions_dict

def check_removals(mempool_removals: List[Coin], removals: Dict[bytes32, CoinRecord]) -> Tuple[Optional[Err], List[Coin]]:
        """
        This function checks for double spends, unknown spends and conflicting transactions in mempool.
        Returns Error (if any), dictionary of Unspents, list of coins with conflict errors (if any any).
        Note that additions are not checked for duplicates, because having duplicate additions requires also
        having duplicate removals.
        """
        conflicts: List[Coin] = []

        for record in removals.values():
            removal = record.coin
            # 1. Checks if it's been spent already
            if record.spent == 1:
                return Err.DOUBLE_SPEND, []
            # 2. Checks if there's a mempool conflict
            if removal.name() in mempool_removals:
                conflicts.append(removal)

        if len(conflicts) > 0:
            return Err.MEMPOOL_CONFLICT, conflicts
        # 5. If coins can be spent return list of unspents as we see them in local storage
        return None, []

def validate_transaction(
    spend_bundle_bytes: bytes,
) -> bytes:
    # constants: ConsensusConstants = dataclass_from_dict(ConsensusConstants, recurse_jsonify(dataclasses.asdict(ConsensusConstants)))
    # Calculate the cost and fees
    program = best_solution_program(SpendBundle.from_bytes(spend_bundle_bytes))
    # npc contains names of the coins removed, puzzle_hashes and their spend conditions
    return bytes(calculate_cost_of_program(program, DEFAULT_CONSTANTS.CLVM_COST_RATIO_CONSTANT, True))

def validate_spendbundle(new_spend: SpendBundle, mempool_removals: List[Coin], current_coin_records: List[CoinRecord], block_height: uint32, validate_signature=True) -> Tuple[Optional[uint64], MempoolInclusionStatus, Optional[Err]]:
    spend_name = new_spend.name()
    cost_result = CostResult.from_bytes(validate_transaction(bytes(new_spend)))

    npc_list = cost_result.npc_list
    cost = cost_result.cost

    if cost > DEFAULT_CONSTANTS.MAX_BLOCK_COST_CLVM:
        return None, MempoolInclusionStatus.FAILED, Err.BLOCK_COST_EXCEEDS_MAX

    if cost_result.error is not None:
        return None, MempoolInclusionStatus.FAILED, Err(cost_result.error)

    removal_names: List[bytes32] = new_spend.removal_names()
    additions = additions_for_npc(npc_list)

    additions_dict: Dict[bytes32, Coin] = {}
    for add in additions:
        additions_dict[add.name()] = add

    addition_amount = uint64(0)
    # Check additions for max coin amount
    for coin in additions:
        if coin.amount > DEFAULT_CONSTANTS.MAX_COIN_AMOUNT:
            return (
                None,
                MempoolInclusionStatus.FAILED,
                Err.COIN_AMOUNT_EXCEEDS_MAXIMUM,
            )
        addition_amount = uint64(addition_amount + coin.amount)

    # Check for duplicate outputs
    addition_counter = collections.Counter(_.name() for _ in additions)
    for k, v in addition_counter.items():
        if v > 1:
            return None, MempoolInclusionStatus.FAILED, Err.DUPLICATE_OUTPUT

    # Check for duplicate inputs
    removal_counter = collections.Counter(name for name in removal_names)
    for k, v in removal_counter.items():
        if v > 1:
            return None, MempoolInclusionStatus.FAILED, Err.DOUBLE_SPEND

    removal_record_dict: Dict[bytes32, CoinRecord] = {}
    removal_coin_dict: Dict[bytes32, Coin] = {}
    unknown_unspent_error: bool = False
    removal_amount = uint64(0)
    for name in removal_names:
        removal_record = list(filter(lambda e: e.coin.name() == name,current_coin_records))
        if len(removal_record) == 0:
            removal_record = None
        else:
            removal_record = removal_record[0]
        if removal_record is None and name not in additions_dict:
            unknown_unspent_error = True
            break
        elif name in additions_dict:
            removal_coin = additions_dict[name]
            # TODO(straya): what timestamp to use here?
            removal_record = CoinRecord(
                removal_coin,
                uint32(self.peak.height + 1),  # In mempool, so will be included in next height
                uint32(0),
                False,
                False,
                uint64(int(time.time())),
            )

        assert removal_record is not None
        removal_amount = uint64(removal_amount + removal_record.coin.amount)
        removal_record_dict[name] = removal_record
        removal_coin_dict[name] = removal_record.coin
    if unknown_unspent_error:
        return None, MempoolInclusionStatus.FAILED, Err.UNKNOWN_UNSPENT

    if addition_amount > removal_amount:
        return None, MempoolInclusionStatus.FAILED, Err.MINTING_COIN

    fees = removal_amount - addition_amount
    assert_fee_sum: uint64 = uint64(0)

    for npc in npc_list:
        if ConditionOpcode.RESERVE_FEE in npc.condition_dict:
            fee_list: List[ConditionVarPair] = npc.condition_dict[ConditionOpcode.RESERVE_FEE]
            for cvp in fee_list:
                fee = int_from_bytes(cvp.vars[0])
                assert_fee_sum = assert_fee_sum + fee
    if fees < assert_fee_sum:
        return (
            None,
            MempoolInclusionStatus.FAILED,
            Err.RESERVE_FEE_CONDITION_FAILED,
        )

    if cost == 0:
        return None, MempoolInclusionStatus.FAILED, Err.UNKNOWN

    # Use this information later when constructing a block
    fail_reason, conflicts = check_removals(mempool_removals, removal_record_dict)
    # If there is a mempool conflict check if this spendbundle has a higher fee per cost than all others
    tmp_error: Optional[Err] = None
    conflicting_pool_items: Dict[bytes32, Coin] = {}
    if fail_reason is Err.MEMPOOL_CONFLICT:
        for conflicting in conflicts:
            # sb: Coin = mempool_removals[conflicting.name()]
            conflicting_pool_items[conflicting.name()] = conflicting

        # for item in conflicting_pool_items.values():
        #     if item.fee_per_cost >= fees_per_cost:
        #         self.add_to_potential_tx_set(new_spend, spend_name, cost_result)
        print("The following items conflict with current mempool items: "+conflicting_pool_items)
        print("This fails in the simulation, but the bigger fee_per_cost likely wins on the network")
        return (
            uint64(cost),
            MempoolInclusionStatus.FAILED,
            Err.MEMPOOL_CONFLICT,
        )

    elif fail_reason:
        return None, MempoolInclusionStatus.FAILED, fail_reason

    if tmp_error:
        return None, MempoolInclusionStatus.FAILED, tmp_error

    # Verify conditions, create hash_key list for aggsig check
    pks: List[G1Element] = []
    msgs: List[bytes32] = []
    error: Optional[Err] = None
    for npc in npc_list:
        coin_record: CoinRecord = removal_record_dict[npc.coin_name]
        # Check that the revealed removal puzzles actually match the puzzle hash
        if npc.puzzle_hash != coin_record.coin.puzzle_hash:
            return None, MempoolInclusionStatus.FAILED, Err.WRONG_PUZZLE_HASH

        chialisp_height = block_height - 1
        error = mempool_check_conditions_dict(coin_record, new_spend, npc.condition_dict, uint32(chialisp_height))

        if error:
            if error is Err.ASSERT_HEIGHT_NOW_EXCEEDS_FAILED or error is Err.ASSERT_HEIGHT_AGE_EXCEEDS_FAILED:
                return uint64(cost), MempoolInclusionStatus.PENDING, error
            break

        if validate_signature:
            for pk, message in pkm_pairs_for_conditions_dict(npc.condition_dict, npc.coin_name):
                pks.append(pk)
                msgs.append(message)

    if error:
        return None, MempoolInclusionStatus.FAILED, error

    if validate_signature:
        # Verify aggregated signature
        if not AugSchemeMPL.aggregate_verify(pks, msgs, new_spend.aggregated_signature):
            return None, MempoolInclusionStatus.FAILED, Err.BAD_AGGREGATE_SIGNATURE

    removals: List[Coin] = [coin for coin in removal_coin_dict.values()]
    # new_item = MempoolItem(new_spend, uint64(fees), cost_result, spend_name, additions, removals)
    # self.mempool.add_to_pool(new_item, additions, removal_coin_dict)
    # log.info(f"add_spendbundle took {time.time() - start_time} seconds")
    return uint64(cost), MempoolInclusionStatus.SUCCESS, None
