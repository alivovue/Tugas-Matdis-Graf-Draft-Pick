import csv
from collections import defaultdict
from itertools import combinations
import networkx as nx
import matplotlib.pyplot as plt

def process_csv_with_matches(filename):
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


def visualize_graph(G, is_directed=False, top_k=None):
    if top_k is not None:
        sorted_edges = sorted(G.edges(data=True), key=lambda x: x[2]['weight'], reverse=True)
        G = G.__class__()  # create new empty graph of same type
        for u, v, d in sorted_edges[:top_k]:
            G.add_edge(u, v, weight=d['weight'])

    pos = nx.spring_layout(G, seed=42)
    weights = [d['weight'] for (_, _, d) in G.edges(data=True)]
    nx.draw(G, pos, with_labels=True, node_color='lightblue', node_size=1000, edge_color=weights,
            edge_cmap=plt.cm.plasma, width=2.5)
    labels = nx.get_edge_attributes(G, 'weight')
    nx.draw_networkx_edge_labels(G, pos, edge_labels={k: f"{v:.1f}" for k, v in labels.items()})
    plt.show()

def main():
    filename = r'd:\Matdis Learning Folder\Makalah matdis\data_draft.csv'
    hero_stats, pair_wins, versus, matches = process_csv_with_matches(filename)
    G_dasar = build_sinergi_dasar_graph(pair_wins, hero_stats)
    G_counter = build_counter_graph_simple(versus)

    print("\nChoose graph to visualize:")
    print("1. Global Synergy Graph")
    print("2. Team Synergy Graph")
    print("3. Counter Graph")
    choice = input("Enter your choice (1/2/3): ").strip()

    if choice == '1':
        G = G_dasar
        is_directed = False
    elif choice == '2':
        team_name = input("Enter team name: ").strip().lower()
        G = build_sinergi_tim_graph(G_dasar, hero_stats, team_name, matches)
        is_directed = False
    elif choice == '3':
        G = G_counter
        is_directed = True
    else:
        print("Invalid choice.")
        return

    print("\nDisplay options:")
    print("1. Show all edges")
    print("2. Show top X edges")
    mode = input("Enter choice (1/2): ").strip()

    if mode == '1':
        visualize_graph(G, is_directed=is_directed)
    elif mode == '2':
        try:
            x = int(input("Enter X: "))
            visualize_graph(G, is_directed=is_directed, top_k=x)
        except:
            print("Invalid X.")
    else:
        print("Invalid display choice.")

if __name__ == "__main__":
    main()
