from parser.parse_scenario import main as parse_scenario_main

def main():
    print("Run started")
    user_input = """One team T1 at a with capacity 4. Resources: b=2. Demand: h=2.
                    Routes: a-b green distance 5, b-h yellow distance 3. Undirected.
                    Safety probs G 0.95, Y 0.70, R 0.30. Objective max_reach_prob
                """
    parse_scenario_main(user_input)


if __name__ == "__main__":
    main()
