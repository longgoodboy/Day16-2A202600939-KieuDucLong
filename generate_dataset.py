import json

data = []
books = ["The Hobbit", "1984", "Dune", "Foundation", "Harry Potter", "Twilight", "The Great Gatsby", "Moby Dick", "To Kill a Mockingbird", "Pride and Prejudice"]
universities = ["Oxford University", "Cambridge", "Harvard", "MIT", "Stanford", "Yale", "Princeton", "Columbia", "Cornell", "Brown"]

# Generate 30 easy
for i in range(30):
    b = books[i % len(books)] + f" Part {i}"
    u = universities[i % len(universities)] + f" branch {i}"
    data.append({
        "qid": f"easy_{i}",
        "difficulty": "easy",
        "question": f"Which university did the author of {b} teach at?",
        "gold_answer": u,
        "context": [
            {"title": f"Author of {b}", "text": f"The author of {b} was a professor at {u}."},
            {"title": u, "text": f"{u} is a great university."}
        ]
    })

# Generate 40 medium
cities = ["London", "Paris", "Berlin", "Tokyo", "New York", "Beijing", "Seoul", "Hanoi", "Rome", "Madrid"]
rivers = ["Thames", "Seine", "Spree", "Sumida", "Hudson", "Yongding", "Han", "Red River", "Tiber", "Manzanares"]
for i in range(40):
    c = cities[i % len(cities)]
    r = rivers[i % len(rivers)]
    p = f"Person_{i}"
    data.append({
        "qid": f"med_{i}",
        "difficulty": "medium",
        "question": f"What river flows through the city where {p} was born?",
        "gold_answer": r,
        "context": [
            {"title": p, "text": f"{p} was born in {c}."},
            {"title": c, "text": f"{c} is crossed by the {r}."}
        ]
    })

# Generate 20 yes/no
for i in range(20):
    p1 = f"Actor_{i}"
    p2 = f"Actress_{i}"
    c1 = "CityA"
    c2 = "CityA" if i % 2 == 0 else "CityB"
    ans = "yes" if c1 == c2 else "no"
    data.append({
        "qid": f"yn_{i}",
        "difficulty": "medium",
        "question": f"Does {p1} share the same birthplace as {p2}?",
        "gold_answer": ans,
        "context": [
            {"title": p1, "text": f"{p1} was born in {c1}."},
            {"title": p2, "text": f"{p2} was born in {c2}."}
        ]
    })

# Generate 15 hard
landmarks = ["Petra", "Machu Picchu", "Colosseum", "Taj Mahal", "Great Wall", "Pyramids", "Stonehenge"]
countries = ["Jordan", "Peru", "Italy", "India", "China", "Egypt", "UK"]
seas = ["Dead Sea", "Pacific Ocean", "Mediterranean", "Indian Ocean", "Yellow Sea", "Red Sea", "North Sea"]
for i in range(15):
    l = landmarks[i % len(landmarks)] + f"_{i}"
    c = countries[i % len(countries)]
    s = seas[i % len(seas)]
    data.append({
        "qid": f"hard_{i}",
        "difficulty": "hard",
        "question": f"What sea borders the country where {l} is located?",
        "gold_answer": s,
        "context": [
            {"title": l, "text": f"{l} is a historical city in {c}."},
            {"title": c, "text": f"{c} borders the {s} to the west."}
        ]
    })

with open("data/my_test_set.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(f"Generated {len(data)} examples.")
