import the_odds

s = set()

events = the_odds.get_events("americanfootball_nfl")

for event in events:
    s.add(event["home_team"])
    s.add(event["away_team"])
    
print(len(s))

print(len(events))

the_odds.get_today_data()