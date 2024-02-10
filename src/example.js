export const quizSrc = {
  lang: "en",
  title: "Cryptography Quizzes",
  author: "TH K\u00f6ln, Schwenk/Knospe",
  info: "",
  questions: [
    {
      title: "Addition",
      error: "",
      variables: ["y", "z", "x"],
      instances: [
        {
          x: { type: "int", value: "12" },
          y: { type: "int", value: "16" },
          z: { type: "int", value: "28" },
        },
        {
          x: { type: "int", value: "12" },
          y: { type: "int", value: "20" },
          z: { type: "int", value: "32" },
        },
        {
          x: { type: "int", value: "19" },
          y: { type: "int", value: "16" },
          z: { type: "int", value: "35" },
        },
        {
          x: { type: "int", value: "15" },
          y: { type: "int", value: "19" },
          z: { type: "int", value: "34" },
        },
        {
          x: { type: "int", value: "10" },
          y: { type: "int", value: "17" },
          z: { type: "int", value: "27" },
        },
      ],
      text: {
        type: "root",
        data: "",
        children: [
          {
            type: "paragraph",
            data: "",
            children: [
              {
                type: "span",
                data: "",
                children: [
                  { type: "text", data: "Calculate ", children: [] },
                  {
                    type: "math",
                    data: "",
                    children: [
                      { type: "var", data: "x", children: [] },
                      { type: "text", data: " + ", children: [] },
                      { type: "var", data: "y", children: [] },
                      { type: "text", data: " =", children: [] },
                    ],
                  },
                  { type: "text", data: " ", children: [] },
                  { type: "input", data: "z", children: [] },
                ],
              },
            ],
          },
        ],
      },
    },
    {
      title: "CPA-Security",
      error: "",
      variables: [],
      instances: [],
      text: {
        type: "root",
        data: "",
        children: [
          {
            type: "paragraph",
            data: "",
            children: [
              {
                type: "span",
                data: "",
                children: [
                  {
                    type: "text",
                    data: "What is true about ",
                    children: [],
                  },
                  {
                    type: "bold",
                    data: "",
                    children: [
                      { type: "text", data: "CPA-secure", children: [] },
                    ],
                  },
                  {
                    type: "text",
                    data: " encryption schemes?",
                    children: [],
                  },
                ],
              },
            ],
          },
          {
            type: "multi-choice",
            data: "",
            children: [
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "true", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "Two encrypted plaintexts cannot be distinguished.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "true", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "CPA-secure schemes are probabilistic.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "false", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "CPA-secure schemes are determinstic.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "true", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "The One-Time-Pad is CPA-secure.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "false", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "Successful Attacks against CPA-secure schemes run in polynomial time.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "false", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "An attacker may win the CPA experiment in ",
                            children: [],
                          },
                          {
                            type: "math",
                            data: "",
                            children: [
                              {
                                type: "text",
                                data: "60\\%",
                                children: [],
                              },
                            ],
                          },
                          {
                            type: "text",
                            data: " of the cases.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "false", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "CPA-secure schemes are perfectly secure.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "true", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "CPA-secure schemes are EAV-secure.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "false", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          {
                            type: "text",
                            data: "CPA-secure schemes are secure against chosen ciphertext attacks.",
                            children: [],
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
            ],
          },
          {
            type: "paragraph",
            data: "",
            children: [
              {
                type: "span",
                data: "",
                children: [
                  { type: "text", data: "TODO another MC", children: [] },
                ],
              },
            ],
          },
          {
            type: "multi-choice",
            data: "",
            children: [
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "false", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          { type: "text", data: "false", children: [] },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "true", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          { type: "text", data: "true", children: [] },
                        ],
                      },
                    ],
                  },
                ],
              },
              {
                type: "answer",
                data: "",
                children: [
                  { type: "bool", data: "true", children: [] },
                  {
                    type: "paragraph",
                    data: "",
                    children: [
                      {
                        type: "span",
                        data: "",
                        children: [
                          { type: "text", data: "true", children: [] },
                        ],
                      },
                    ],
                  },
                ],
              },
            ],
          },
          {
            type: "paragraph",
            data: "",
            children: [
              {
                type: "span",
                data: "",
                children: [
                  { type: "text", data: "an itemization:", children: [] },
                ],
              },
            ],
          },
          {
            type: "itemize",
            data: "",
            children: [
              {
                type: "paragraph",
                data: "",
                children: [
                  {
                    type: "span",
                    data: "",
                    children: [{ type: "text", data: "bla", children: [] }],
                  },
                ],
              },
              {
                type: "paragraph",
                data: "",
                children: [
                  {
                    type: "span",
                    data: "",
                    children: [{ type: "text", data: "blub", children: [] }],
                  },
                ],
              },
            ],
          },
        ],
      },
    },
    {
      title: "Vigen\u00e8re Cipher: Encryption",
      error: "",
      variables: [
        "c1",
        "m4",
        "k2",
        "c4",
        "c5",
        "c2",
        "m3",
        "m5",
        "m2",
        "c3",
        "k1",
        "m1",
      ],
      instances: [
        {
          m1: { type: "int", value: "12" },
          m2: { type: "int", value: "23" },
          m3: { type: "int", value: "21" },
          m4: { type: "int", value: "9" },
          m5: { type: "int", value: "23" },
          k1: { type: "int", value: "1" },
          k2: { type: "int", value: "4" },
          c1: { type: "int", value: "13" },
          c2: { type: "int", value: "1" },
          c3: { type: "int", value: "22" },
          c4: { type: "int", value: "13" },
          c5: { type: "int", value: "24" },
        },
        {
          m1: { type: "int", value: "6" },
          m2: { type: "int", value: "15" },
          m3: { type: "int", value: "10" },
          m4: { type: "int", value: "9" },
          m5: { type: "int", value: "8" },
          k1: { type: "int", value: "1" },
          k2: { type: "int", value: "5" },
          c1: { type: "int", value: "7" },
          c2: { type: "int", value: "20" },
          c3: { type: "int", value: "11" },
          c4: { type: "int", value: "14" },
          c5: { type: "int", value: "9" },
        },
        {
          m1: { type: "int", value: "3" },
          m2: { type: "int", value: "25" },
          m3: { type: "int", value: "2" },
          m4: { type: "int", value: "19" },
          m5: { type: "int", value: "20" },
          k1: { type: "int", value: "3" },
          k2: { type: "int", value: "4" },
          c1: { type: "int", value: "6" },
          c2: { type: "int", value: "3" },
          c3: { type: "int", value: "5" },
          c4: { type: "int", value: "23" },
          c5: { type: "int", value: "23" },
        },
        {
          m1: { type: "int", value: "6" },
          m2: { type: "int", value: "25" },
          m3: { type: "int", value: "7" },
          m4: { type: "int", value: "2" },
          m5: { type: "int", value: "13" },
          k1: { type: "int", value: "2" },
          k2: { type: "int", value: "4" },
          c1: { type: "int", value: "8" },
          c2: { type: "int", value: "3" },
          c3: { type: "int", value: "9" },
          c4: { type: "int", value: "6" },
          c5: { type: "int", value: "15" },
        },
        {
          m1: { type: "int", value: "23" },
          m2: { type: "int", value: "4" },
          m3: { type: "int", value: "24" },
          m4: { type: "int", value: "22" },
          m5: { type: "int", value: "6" },
          k1: { type: "int", value: "2" },
          k2: { type: "int", value: "4" },
          c1: { type: "int", value: "25" },
          c2: { type: "int", value: "8" },
          c3: { type: "int", value: "0" },
          c4: { type: "int", value: "0" },
          c5: { type: "int", value: "8" },
        },
      ],
      text: {
        type: "root",
        data: "",
        children: [
          {
            type: "paragraph",
            data: "",
            children: [
              {
                type: "span",
                data: "",
                children: [
                  { type: "text", data: "Encrypt ", children: [] },
                  {
                    type: "math",
                    data: "",
                    children: [
                      { type: "text", data: "m=(", children: [] },
                      { type: "var", data: "m1", children: [] },
                      { type: "text", data: ",", children: [] },
                      { type: "var", data: "m2", children: [] },
                      { type: "text", data: ",", children: [] },
                      { type: "var", data: "m3", children: [] },
                      { type: "text", data: ",", children: [] },
                      { type: "var", data: "m4", children: [] },
                      { type: "text", data: ",", children: [] },
                      { type: "var", data: "m5", children: [] },
                      { type: "text", data: ")", children: [] },
                    ],
                  },
                  { type: "text", data: " using the key ", children: [] },
                  {
                    type: "math",
                    data: "",
                    children: [
                      { type: "text", data: "k=(", children: [] },
                      { type: "var", data: "k1", children: [] },
                      { type: "text", data: ",", children: [] },
                      { type: "var", data: "k2", children: [] },
                      { type: "text", data: ")", children: [] },
                    ],
                  },
                  { type: "text", data: ".", children: [] },
                ],
              },
            ],
          },
          {
            type: "itemize",
            data: "",
            children: [
              {
                type: "paragraph",
                data: "",
                children: [
                  {
                    type: "span",
                    data: "",
                    children: [
                      {
                        type: "math",
                        data: "",
                        children: [{ type: "text", data: "c=(", children: [] }],
                      },
                      { type: "text", data: " ", children: [] },
                      { type: "input", data: "c1", children: [] },
                      { type: "text", data: ", ", children: [] },
                      { type: "input", data: "c2", children: [] },
                      { type: "text", data: ", ", children: [] },
                      { type: "input", data: "c3", children: [] },
                      { type: "text", data: ", ", children: [] },
                      { type: "input", data: "c4", children: [] },
                      { type: "text", data: ", ", children: [] },
                      { type: "input", data: "c5", children: [] },
                      { type: "text", data: " ", children: [] },
                      {
                        type: "math",
                        data: "",
                        children: [{ type: "text", data: ")", children: [] }],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    },
  ],
};
