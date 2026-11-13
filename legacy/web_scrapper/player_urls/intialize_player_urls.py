import requests
from html.parser import HTMLParser
import sys

def get_web_page(url):
    return requests.get(url).content.decode('utf-8')

class PlayerUrlParser(HTMLParser):
    def __init__(self):
        super().__init__()     
        self.in_td_tag = False
        self.in_span_tag = False
        self.start_of_data = False
        self.is_player_name = 0
        self.players = []
    
    def handle_starttag(self, tag, attrs):         
        if tag == 'td':
            self.in_td_tag = True
         
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td_tag = False    

    def handle_data(self, data):
        if self.in_td_tag:
            try: # data starts recording when a number is encountered
                int(data)
                self.start_of_data = True        
            except ValueError:
                pass
            if self.start_of_data:
                self.is_player_name += 1
                if self.is_player_name == 2:                    
                    data = data.replace('\'', '')
                    data = data.replace(' Jr.', '')
                    data = data.replace('.', '')
                    data = data.replace(' III', '') 
                    data = data.replace(' II', '')                                    
                    data = data.replace(' ', '-')  
                    self.players.append(f"{data.lower()}")
                if data[-1] == '%':    
                    self.is_player_name = 0    

class PlayerURLErrorsParser(HTMLParser):
    def __init__(self, player):
        super().__init__()     
        self.in_td_tag = False
        self.in_span_tag = False
        self.start_of_data = 0
        self.player = player
         
    def handle_starttag(self, tag, attrs):         
        if tag == 'td':
            self.in_td_tag = True
         
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td_tag = False    

    def handle_data(self, data):     
        if self.in_td_tag:
            if self.start_of_data == 3:
                if data[:2] != f'{sys.argv[1]}'.upper():
                    self.player = f'{self.player}-{sys.argv[1]}'               
            self.start_of_data += 1

class ValidatePlayerURLParser(HTMLParser):
    def __init__(self, player, output):
        super().__init__()     
        self.in_td_tag = False
        self.in_span_tag = False
        self.start_of_data = 0
        self.players = []
        self.player = player
        self.output = output
         
    def handle_starttag(self, tag, attrs):         
        if tag == 'td':
            self.in_td_tag = True
         
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td_tag = False    

    def handle_data(self, data):     
        if self.in_td_tag:
            if self.start_of_data == 3:
                if data[:2] == f'{sys.argv[1]}'.upper():
                    self.output.write(f'{self.player}\n')               
            self.start_of_data += 1

def main(output_file = f'web_scrapper/player_urls/player_urls_{sys.argv[1]}.out'):
    player_url_parser = PlayerUrlParser()
    player_url_parser.feed(get_web_page(f'https://www.fantasypros.com/nfl/stats/{sys.argv[1]}.php'))
    
    with open(output_file, 'w') as output: 
        for player in player_url_parser.players:
            player_url_errors_parser = PlayerURLErrorsParser(player)         
            player_url_errors_parser.feed(get_web_page(f'https://www.fantasypros.com/nfl/rankings/{player}.php'))

            validate_player_url_parser = ValidatePlayerURLParser(player_url_errors_parser.player, output)
            validate_player_url_parser.feed(get_web_page(f'https://www.fantasypros.com/nfl/rankings/{player_url_errors_parser.player}.php'))
                   
if __name__ == '__main__':
    main()
 
 