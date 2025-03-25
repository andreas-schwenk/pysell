"""
Converts the pySELL examples to SQL queries for the question poll
at https://pysell.org
"""

import glob
import os
import tempfile
import time
import json
import sell

# print(os.getcwd())

question_cnt = 0

output = ""

with tempfile.TemporaryDirectory() as temp_dir:
    print(f"Temporary directory: {temp_dir}")

    src_files = ["examples/ex1.txt"]
    src_files.extend(sorted(glob.glob("examples/EN/*.txt")))
    src_files.extend(sorted(glob.glob("examples/DE/*.txt")))

    for src_path in src_files:
        print("Processing file: " + src_path)
        with open(src_path, "r", encoding="utf-8") as file:
            lines = file.readlines()
            lang = ""
            title = ""
            author = ""
            topic = []
            questions = []
            question = ""
            for line in lines:
                line = line.replace("\n", "").split("#")[0] + "\n"
                if line.startswith("LANG"):
                    lang = line[4:].strip()
                elif line.startswith("TITLE"):
                    title = line[5:].strip()
                elif line.startswith("AUTHOR"):
                    author = line[6:].strip()
                elif line.startswith("TOPIC"):
                    topic_src = line[5:].strip().split("--")
                    topic = [s.strip() for s in topic_src]
                elif line.startswith("QUESTION"):
                    if len(question.strip()) > 0:
                        questions.append(question)
                    question = line
                else:
                    question += line
            if len(question.strip()) > 0:
                questions.append(question)

            questions = [(q.strip() + "\n") for q in questions]

            topic1 = "" if len(topic) < 1 else topic[0]
            topic2 = "" if len(topic) < 2 else topic[1]
            topic3 = "" if len(topic) < 3 else topic[2]
            topic4 = "" if len(topic) < 4 else topic[3]
            created = int(time.time())
            modified = int(time.time())

            for question in questions:

                temp_src_path = os.path.join(temp_dir, "question.txt")
                temp_json_path = os.path.join(temp_dir, "question.json")
                with open(temp_src_path, "w", encoding="utf-8") as f2:
                    question_with_metadata = (
                        "LANG " + lang + "\n" + "AUTHOR " + author + "\n\n" + question
                    )
                    f2.write(question_with_metadata)

                sell.main(["sell.py", "-J", "-S", temp_src_path])

                with open(temp_json_path, "r", encoding="utf-8") as f2:
                    json_obj = json.load(f2)

                q = json_obj["questions"][0]
                title = q["title"]

                print("... question: '" + title + "'")
                question_cnt += 1

                del q["src_line"]
                del q["text_src_html"]
                del q["python_src_html"]
                del q["python_src_tokens"]

                src_str = (
                    json.dumps(question, ensure_ascii=False)
                    # .replace('\\"', '\\\\"')
                    .replace("'", "''")[1:-1]
                )

                json_str = json.dumps(json_obj, ensure_ascii=False)
                json_str = json_str.replace("\\\\", "\\\\\\\\")
                json_str = json_str.replace('\\"', '\\\\"')
                json_str = json_str.replace("'", "''")

                sql = f"""
INSERT INTO question (
    topic1, topic2, topic3, topic4, title, lang, author, created, modified, src, json, user
) VALUES (
    '{topic1}',
    '{topic2}',
    '{topic3}',
    '{topic4}',
    '{title}',
    '{lang}',
    '{author}',
    {created},
    {modified},
    '{src_str}',
    '{json_str}',
    0
);
"""
                if title != "Images":
                    # TODO: fix this example from ex1.txt
                    output += sql + "\n\n"


with open("platforms/pysell_org/tools/questions.sql", "w", encoding="utf-8") as f2:
    f2.write(output)

print("PROCESSED " + str(question_cnt) + " QUESTIONS IN TOTAL")
