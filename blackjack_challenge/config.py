from decimal import Decimal

# Shoe
DEFAULT_DECK_COUNT = 6
VALID_DECK_COUNTS = (6, 8)
SHUFFLE_THRESHOLD = 0.25  # reshuffle when 25% of shoe remains

# 10-value card rank order for Blackjack payout comparison (higher = better)
TEN_CARD_RANK_ORDER = {
    "10": 1,
    "J":  2,
    "Q":  3,
    "K":  4,
}

# Base game payouts (multiplier on wager; player also gets wager back)
PAYOUT_BJ_NO_DEALER_BJ      = Decimal("2")   # 2:1
PAYOUT_BJ_VS_BJ_LOWER_RANK  = Decimal("5")   # 5:1  dealer rank < player rank
PAYOUT_BJ_VS_BJ_SAME_RANK   = Decimal("4")   # 4:1
PAYOUT_BJ_VS_BJ_HIGHER_RANK = Decimal("3")   # 3:1  dealer rank > player rank
PAYOUT_EVEN_MONEY            = Decimal("1")   # 1:1

# Side bet payouts — Star Pairs
PAYOUT_STAR_MIXED            = Decimal("5")
PAYOUT_STAR_SAME_COLOUR      = Decimal("8")
PAYOUT_STAR_SUITED           = Decimal("20")
PAYOUT_STAR_PAIR_OF_ACES     = Decimal("30")

BLAZING_7S_ENTRY             = Decimal("2.50")
BLAZING_7S_JACKPOT_MIN       = Decimal("25000")
BLAZING_7S_PAYOUTS = {
    "one_player_seven_one_dealer":  Decimal("25"),
    "two_player_sevens":            Decimal("50"),
    "three_sevens":                 Decimal("500"),
    "three_coloured_sevens":        Decimal("1250"),
    "three_suited_sevens_jackpot":  Decimal("0.10"),  # 10% of jackpot
    "three_7s_of_diamonds_jackpot": Decimal("1.00"),  # 100% of jackpot
}

# Table limits
MIN_BET = Decimal("5")
MAX_BET = Decimal("10000")
MAX_SIDE_BET = Decimal("500")
MAX_SPLITS = 2  # max splits per box (results in 3 hands)
