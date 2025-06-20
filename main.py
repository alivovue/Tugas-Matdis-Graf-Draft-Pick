import csv
import math
from collections import defaultdict
from itertools import combinations, product
import networkx as nx

def build_sinergi_dasar_graph(pair_wins, hero_stats):
    G = nx.Graph()
    for (h1, h2), stats in pair_wins.items():
        win = stats['win']
        lose = stats['lose']
        total = win + lose
        base_weight = 0.6 * win + 0.3 * lose

        if base_weight == 0:
            # Use hero with fewer total picks
            pick_i = hero_stats[h1]['pick_win'] + hero_stats[h1]['pick_lose']
            pick_j = hero_stats[h2]['pick_win'] + hero_stats[h2]['pick_lose']
            if pick_i == 0 and pick_j == 0:
                continue
            elif pick_i == 0:
                base_weight = 0.1 * (hero_stats[h1]['pick_win'] / 1)
            elif pick_j == 0:
                base_weight = 0.1 * (hero_stats[h2]['pick_win'] / 1)
            else:
                hero = h1 if pick_i < pick_j else h2
                total_picks = hero_stats[hero]['pick_win'] + hero_stats[hero]['pick_lose']
                if total_picks > 0:
                    winrate = hero_stats[hero]['pick_win'] / total_picks
                    base_weight = 0.1 * winrate

        if base_weight > 0:
            G.add_edge(h1, h2, weight=base_weight)

    return G


def build_sinergi_tim_graph(G_dasar, hero_stats, team_name, matches):
    hero_team_weights = defaultdict(float)

    for match in matches:
        if team_name not in match['teams']:
            continue
        team_data = match['teams'][team_name]
        enemy_team = [t for t in match['teams'] if t != team_name]
        if not enemy_team:
            continue
        enemy_data = match['teams'][enemy_team[0]]

        for hero in set(team_data['pick']):
            if team_data['is_winner']:
                hero_team_weights[hero] += 0.3
            else:
                hero_team_weights[hero] += 0.2

        for hero in set(enemy_data['ban']):
            hero_team_weights[hero] += 0.5

    G_tim = G_dasar.copy()

    for node in G_tim.nodes:
        if node in hero_team_weights:
            for neighbor in G_tim.neighbors(node):
                if G_tim.has_edge(node, neighbor):
                    G_tim[node][neighbor]['weight'] += hero_team_weights[node]

    return G_tim


def build_counter_graph_simple(versus):
    G = nx.DiGraph()
    for (h1, h2), stats in versus.items():
        win = stats['win']
        lose = stats['lose']
        score = win - lose
        if score > 0:
            G.add_edge(h1, h2, weight=score)
        elif score < 0:
            G.add_edge(h2, h1, weight=-score)
    return G


def get_top_edges(G, top_k=50):
    edges = sorted(G.edges(data=True), key=lambda x: x[2]['weight'], reverse=True)
    return edges[:top_k]


# Re-process data with extra matches info
def process_csv_with_matches(filename):
    team_picks = defaultdict(list)
    hero_stats = defaultdict(lambda: {'pick_win': 0, 'pick_lose': 0, 'banned': 0})
    pair_wins = defaultdict(lambda: {'win': 0, 'lose': 0, 'freq': 0})
    versus = defaultdict(lambda: {'win': 0, 'lose': 0})
    matches = []

    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        match_data = defaultdict(lambda: {'teams': defaultdict(dict)})

        for row in reader:
            match_id = row['match_id']
            team = row['team']
            hero = row['hero'].strip().lower()
            is_winner = int(row['is_winner'])
            action = row['action_type']

            match = match_data[match_id]
            if team not in match['teams']:
                match['teams'][team] = {'pick': [], 'ban': [], 'is_winner': is_winner}

            if action == 'pick':
                match['teams'][team]['pick'].append(hero)
            elif action == 'ban':
                match['teams'][team]['ban'].append(hero)

        for match_id, match in match_data.items():
            teams = list(match['teams'].keys())
            if len(teams) != 2:
                continue
            t1, t2 = teams
            t1_data = match['teams'][t1]
            t2_data = match['teams'][t2]

            # Store match
            matches.append({'teams': {t1: t1_data, t2: t2_data}})

            for team_data in [t1_data, t2_data]:
                for hero in team_data['ban']:
                    hero_stats[hero]['banned'] += 1
                for hero in team_data['pick']:
                    if team_data['is_winner']:
                        hero_stats[hero]['pick_win'] += 1
                    else:
                        hero_stats[hero]['pick_lose'] += 1

            for team_data in [t1_data, t2_data]:
                picks = team_data['pick']
                for h1, h2 in combinations(sorted(picks), 2):
                    pair = tuple(sorted((h1, h2)))
                    pair_wins[pair]['freq'] += 1
                    if team_data['is_winner']:
                        pair_wins[pair]['win'] += 1
                    else:
                        pair_wins[pair]['lose'] += 1

            for h1 in t1_data['pick']:
                for h2 in t2_data['pick']:
                    if t1_data['is_winner']:
                        versus[(h1, h2)]['win'] += 1
                    else:
                        versus[(h1, h2)]['lose'] += 1
            for h1 in t2_data['pick']:
                for h2 in t1_data['pick']:
                    if t2_data['is_winner']:
                        versus[(h1, h2)]['win'] += 1
                    else:
                        versus[(h1, h2)]['lose'] += 1

    return hero_stats, pair_wins, versus, matches


# Run full pipeline for sample team
filename = r'd:\Matdis Learning Folder\Makalah matdis\data_draft.csv'
hero_stats, pair_wins, versus, matches = process_csv_with_matches(filename)

# Build graphs
G_dasar = build_sinergi_dasar_graph(pair_wins, hero_stats)
G_counter = build_counter_graph_simple(versus)
G_tim = build_sinergi_tim_graph(G_dasar, hero_stats, "onic", matches)

# Get top 50 edges
top_dasar = get_top_edges(G_dasar, top_k=50)
top_tim = get_top_edges(G_tim, top_k=50)
top_counter = get_top_edges(G_counter, top_k=50)

def hero_value(hero, team_graph, counter_graph, team_allies, enemy_heroes):
    # Total sinergi value (sum of all edges connected to hero)
    sinergi_val = sum(
        team_graph[hero][nb]['weight'] for nb in team_graph.neighbors(hero)
        if team_graph.has_edge(hero, nb)
    )

    # Counter value
    counter_val = 0
    for enemy in enemy_heroes:
        if counter_graph.has_edge(hero, enemy):  # A counters enemy
            counter_val += counter_graph[hero][enemy]['weight']
        if counter_graph.has_edge(enemy, hero):  # Enemy counters A
            counter_val -= counter_graph[enemy][hero]['weight']

    return sinergi_val + counter_val

# Map hero to lanes (you must define this mapping based on your game)
hero_to_lanes = defaultdict(set)
hero_to_lanes = {
    'akai': {'exp'},
    'alpha': {'jungler'},
    'angela': {'roam'},
    'arlott': {'exp'},
    'aurora': {'mid'},
    'badang': {'exp', 'roam'},
    'barats': {'jungler'},
    'baxia': {'exp', 'jungler', 'roam'},
    'beatrix': {'gold'},
    'belerick': {'exp'},
    'benedetta': {'exp'},
    'bruno': {'gold'},
    'carmilla': {'roam'},
    'cecilion': {'mid'},
    'chip': {'roam'},
    'chou': {'exp', 'roam'},
    'cici': {'exp'},
    'claude': {'gold'},
    'clint': {'gold'},
    'edith': {'exp'},
    'esmeralda': {'exp'},
    'fanny': {'jungler'},
    'faramis': {'mid'},
    'floryn': {'roam'},
    'franco': {'roam'},
    'fredrinn': {'exp', 'jungler'},
    'gatotkaca': {'exp', 'roam'},
    'gloo': {'exp'},
    'granger': {'gold'},
    'guinevere': {'jungler', 'roam'},
    'hanzo': {'gold', 'jungler'},
    'harith': {'gold'},
    'hayabusa': {'jungler'},
    'helcurt': {'roam'},
    'hilda': {'exp', 'mid', 'roam'},
    'hylos': {'exp', 'roam'},
    'irithel': {'gold'},
    'jawhead': {'roam'},
    'joy': {'jungler'},
    'julian': {'jungler'},
    'kadita': {'mid'},
    'kaja': {'jungler'},
    'kalea': {'exp', 'roam'},
    'karrie': {'gold'},
    'khaleed': {'exp', 'roam'},
    'khufra': {'roam'},
    'kimmy': {'gold', 'mid'},
    'lancelot': {'jungler'},
    'leomord': {'jungler'},
    'ling': {'jungler'},
    'lukas': {'exp', 'jungler'},
    'lunox': {'gold', 'mid'},
    'luo yi': {'mid'},
    'lylia': {'mid'},
    'martis': {'jungler'},
    'masha': {'exp'},
    'mathilda': {'exp', 'roam'},
    'moskov': {'gold'},
    'natan': {'gold'},
    'nolan': {'jungler'},
    'novaria': {'mid', 'roam'},
    'paquito': {'exp'},
    'pharsa': {'mid'},
    'phoveus': {'exp'},
    'ruby': {'exp', 'gold', 'roam'},
    'selena': {'mid'},
    'suyou': {'jungler'},
    'terizla': {'exp'},
    'tigreal': {'roam'},
    'uranus': {'exp'},
    'vale': {'mid'},
    'valentina': {'exp', 'mid'},
    'valir': {'mid'},
    'vexana': {'mid'},
    'wanwan': {'gold'},
    'xborg': {'exp', 'jungler'},
    'yi sun shin': {'jungler'},
    'yve': {'mid'},
    'zhask': {'mid'},
    'zhuxin': {'mid'}
}
# Example: hero_to_lanes['granger'] = {'gold'}, hero_to_lanes['chou'] = {'roam', 'exp'}

def get_effective_lane_occupation(picked_heroes):
    lane_count = defaultdict(int)
    fixed_heroes = []
    flexible_heroes = []

    for hero in picked_heroes:
        lanes = hero_to_lanes.get(hero, set())
        if len(lanes) == 1:
            lane = next(iter(lanes))
            lane_count[lane] += 1
            fixed_heroes.append((hero, lanes))
        elif len(lanes) > 1:
            flexible_heroes.append((hero, lanes))

    # Alokasikan hero fleksibel ke lane yang belum penuh
    for hero, lanes in flexible_heroes:
        for lane in sorted(lanes):  # prioritaskan berdasarkan urutan abjad
            if lane_count[lane] == 0:
                lane_count[lane] += 1
                break

    return set(lane_count.keys())

def recommend_heroes(action_type, team_name, enemy_team, our_picks, our_bans, enemy_picks, enemy_bans):
    team_graph = build_sinergi_tim_graph(G_dasar, hero_stats, team_name, matches)
    enemy_graph = build_sinergi_tim_graph(G_dasar, hero_stats, enemy_team, matches)

    picked_or_banned = set(our_picks + our_bans + enemy_picks + enemy_bans)
    # occupied_lanes = set()
    # enemy_occupied_lanes = set()
    # for hero in our_picks:
    #     occupied_lanes.update(hero_to_lanes.get(hero, set()))
    # for hero in enemy_picks:
    #     enemy_occupied_lanes.update(hero_to_lanes.get(hero, set()))
    occupied_lanes = get_effective_lane_occupation(our_picks)
    enemy_occupied_lanes = get_effective_lane_occupation(enemy_picks)

    scores = {}

    for hero in G_dasar.nodes:
        if hero in picked_or_banned:
            continue

        if action_type == 'pick':
            value = hero_value(hero, team_graph, G_counter, our_picks, enemy_picks)
        elif action_type == 'ban':
            value = hero_value(hero, enemy_graph, G_counter, enemy_picks, our_picks)
        else:
            continue

        scores[hero] = value

    # Sort heroes by value descending
    sorted_heroes = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Filter top 5 based on lane availability and already picked/banned
    top_valid = []
    for hero, score in sorted_heroes:
        if hero in picked_or_banned:
            continue
        lanes = hero_to_lanes.get(hero, set())

        if not lanes:
            top_valid.append((hero, score))
        elif action_type == 'pick':
            if not lanes.isdisjoint({'exp', 'gold', 'mid', 'jungler', 'roam'} - occupied_lanes):
                top_valid.append((hero, score))
        elif action_type == 'ban':
            if len(lanes) == 1 and next(iter(lanes)) in enemy_occupied_lanes:
                continue  # hero hanya bisa di 1 lane dan sudah diambil musuh
            if not lanes <= enemy_occupied_lanes:
                top_valid.append((hero, score))

        if len(top_valid) >= 5:
            break

    print(f"\nTop 5 hero recommendations for {action_type.upper()}:")
    for hero, score in top_valid:
        print(f"{hero} : {score:.4f}")


# Example usage
team_name = input("Masukkan nama tim kita: ").strip().lower()
enemy_team = input("Masukkan nama tim lawan: ").strip().lower()

print("Masukkan hero yang sudah kita PICK (pisah dengan koma):")
our_picks = [h.strip().lower() for h in input().split(',') if h.strip()]
print("Masukkan hero yang sudah kita BAN (pisah dengan koma):")
our_bans = [h.strip().lower() for h in input().split(',') if h.strip()]
print("Masukkan hero yang sudah DIPICK musuh:")
enemy_picks = [h.strip().lower() for h in input().split(',') if h.strip()]
print("Masukkan hero yang sudah DIBAN musuh:")
enemy_bans = [h.strip().lower() for h in input().split(',') if h.strip()]

# Combine all picked/banned to filter them out
picked_or_banned_total = set(our_picks + our_bans + enemy_picks + enemy_bans)

act = input("Apakah ini tahap PICK atau BAN? (pick/ban): ").strip().lower()

recommend_heroes(act, team_name, enemy_team, our_picks, our_bans, enemy_picks, enemy_bans)