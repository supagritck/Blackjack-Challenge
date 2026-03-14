from blackjack_challenge.ui import display, prompts
from blackjack_challenge.models.player import Player
from blackjack_challenge.game.engine import GameEngine


def main():
    display.print_welcome()
    name = prompts.get_player_name()
    balance = prompts.get_starting_balance()
    num_decks = prompts.get_num_decks()

    player = Player(name=name, balance=balance)
    engine = GameEngine(player=player, num_decks=num_decks)
    engine.run()


if __name__ == "__main__":
    main()
