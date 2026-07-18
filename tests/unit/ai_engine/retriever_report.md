# Retriever 检索结果报告

> 由 `tests/unit/ai_engine/demo_retriever.py` 生成。使用真实题库（`data/questions.db`）+ 向量库（`data/chroma/`）+ Qwen3-Embedding-4B。种子固定为 42，SQL 随机路径可复现。

共 10 个样例，覆盖 Retriever 的全部路径：属性配额分桶、KP 硬过滤（三种题型）、向量语义检索（RAG，多主题）、KP+语义组合、shortfall 兜底、全库随机。

## 样例 1：5 单选 + 5 改写

- **用户诉求**：「5 道单选 + 5 道改写」
- **检索路径**：配额分桶 · SQL 随机
- **GenerateRequest**：`total_questions=10`<br>`question_types=[]`<br>`knowledge_points=[]`<br>`type_distribution={'single_choice': 5, 'sentence_rewriting': 5}`<br>`free_text=''`
- **结果**：取到 10 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00786 | single_choice | — (随机) | Close your eyes and________you are sitting on a cloud.How do you feel？ |
| 2 | q_00637 | single_choice | — (随机) | ________quickly Lucy can do her work on the computer！ |
| 3 | q_00709 | single_choice | — (随机) | Because of the spread of the disease，our flight to France________last week. |
| 4 | q_00641 | single_choice | — (随机) | ________exciting form of dance Tap dancing is！ |
| 5 | q_00512 | single_choice | — (随机) | Which of the following underlined parts is different in pronunciation from the others？ |
| 6 | q_00441 | sentence_rewriting | — (随机) | It is fun to enjoy the autumn leaves in Beijing. |
| 7 | q_00998 | sentence_rewriting | — (随机) | Our country sent a medical team to Italy two months ago. |
| 8 | q_00435 | sentence_rewriting | — (随机) | Kitty rarely went to bed after 11 o'clock. |
| 9 | q_00484 | sentence_rewriting | — (随机) | The two men managed to escape from the prison at last. |
| 10 | q_00985 | sentence_rewriting | — (随机) | The hard cover notebook on the teacher's desk is <u>Jackie's</u>. |

## 样例 2：8 道时态单选

- **用户诉求**：「8 道时态的单选题」
- **检索路径**：KP 硬过滤 · SQL 随机
- **GenerateRequest**：`total_questions=8`<br>`question_types=['single_choice']`<br>`knowledge_points=['kp_sc_verbs']`<br>`type_distribution={}`<br>`free_text=''`
- **结果**：取到 8 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00700 | single_choice | — (随机) | —Excuse me，what time does Flight KA897leave？ |
| 2 | q_00696 | single_choice | — (随机) | The discussion________for nearly twenty minutes when I arrived at the meeting. |
| 3 | q_00188 | single_choice | — (随机) | Terry gets up at 6:30 every morning and then he________a bath. |
| 4 | q_00179 | single_choice | — (随机) | The Walt Disney Company________6 theme parks since 1955. |
| 5 | q_00687 | single_choice | — (随机) | The electricity went off while I________with my mother in the sitting room last night. |
| 6 | q_00704 | single_choice | — (随机) | The invitation letter________to Charles and his wife the day before yesterday. |
| 7 | q_00718 | single_choice | — (随机) | Mobile phones________in our daily life now，like making phone calls，paying and reading. |
| 8 | q_00168 | single_choice | — (随机) | —Look!My mother________a new hat for me. |

## 样例 3：关于环保的单选

- **用户诉求**：「来几道关于环保的单选」
- **检索路径**：向量语义检索 · RAG
- **GenerateRequest**：`total_questions=5`<br>`question_types=['single_choice']`<br>`knowledge_points=[]`<br>`type_distribution={}`<br>`free_text='关于环保 环境保护 污染'`
- **结果**：取到 5 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00583 | single_choice | 0.572 | This car is environmentally friendly，because it causes very little________. |
| 2 | q_00093 | single_choice | 0.564 | From now on，we have to reduce the air pollution and care________our environment. |
| 3 | q_00595 | single_choice | 0.423 | More and more people choose the style of a low－carbon life and the air is getting much____ |
| 4 | q_00554 | single_choice | 0.394 | —Would you like to see the hit film called TheWandering Earthor go shopping this weekend？ |
| 5 | q_00809 | single_choice | 0.389 | —Look at the sign.You should throw the rubbish into the right dustbin. |

## 样例 4：冷门 KP 超量请求

- **用户诉求**：「多出点其他类的题（映射到冷门 KP）」
- **检索路径**：shortfall 兜底（库仅 2 道，要 50 道）
- **GenerateRequest**：`total_questions=50`<br>`question_types=['single_choice']`<br>`knowledge_points=['kp_sc_misc']`<br>`type_distribution={}`<br>`free_text=''`
- **结果**：取到 2 道，**shortfall = {'single_choice': 48}**

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00287 | single_choice | — (随机) | ________a hole in the door.Otherwise，he couldn't see what happened inside the room. |
| 2 | q_00286 | single_choice | — (随机) | According to Arthur Conan Doyle，where did Sherlock Holmes live in London? |

> ⚠ bucket 'single_choice' short of 48 question(s) (needed 50, found 2)

## 样例 5：随便 5 道

- **用户诉求**：「随便来 5 道」
- **检索路径**：无过滤 · 全库随机
- **GenerateRequest**：`total_questions=5`<br>`question_types=[]`<br>`knowledge_points=[]`<br>`type_distribution={}`<br>`free_text=''`
- **结果**：取到 5 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00684 | single_choice | — (随机) | When Julia________The Adventures of Tom Sawyer，the light suddenly went out. |
| 2 | q_00263 | single_choice | — (随机) | —Would you mind changing seats with me? |
| 3 | q_00623 | single_choice | — (随机) | More and more people go to work________public transport instead of driving private cars. |
| 4 | q_00156 | single_choice | — (随机) | Sorry for the inconvenience，for the workers________the museum at the moment. |
| 5 | q_00051 | single_choice | — (随机) | ________people gathered to pay respect to the firefighters who died while putting out the  |

## 样例 6：6 道名词复数（词性转换）

- **用户诉求**：「来 6 道名词变复数的词性转换」
- **检索路径**：KP 硬过滤 · SQL 随机（词性转换题型）
- **GenerateRequest**：`total_questions=6`<br>`question_types=['word_form']`<br>`knowledge_points=['kp_wf_noun_plural']`<br>`type_distribution={}`<br>`free_text=''`
- **结果**：取到 6 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00830 | word_form | — (随机) | I'm fond of eating fruit.Mangoes and________are my favourite. |
| 2 | q_00300 | word_form | — (随机) | As a good detective，Ken looks for clues carefully and never jumps to________. |
| 3 | q_00297 | word_form | — (随机) | The boy could not sleep，and he began to count________，but failed. |
| 4 | q_00840 | word_form | — (随机) | People are wearing masks to cover their________and noses to prevent smog. |
| 5 | q_00833 | word_form | — (随机) | Robben owns some furniture________in Wuhan. |
| 6 | q_00294 | word_form | — (随机) | Jenny was happy to find some________of chocolate in her bag. |

## 样例 7：5 道被动语态改写

- **用户诉求**：「出 5 道被动语态的改写句子」
- **检索路径**：KP 硬过滤 · SQL 随机（改写题型）
- **GenerateRequest**：`total_questions=5`<br>`question_types=['sentence_rewriting']`<br>`knowledge_points=['kp_sr_passive_voice']`<br>`type_distribution={}`<br>`free_text=''`
- **结果**：取到 5 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_01000 | sentence_rewriting | — (随机) | So far scientists have done a lot of research on Mars successfully. |
| 2 | q_00996 | sentence_rewriting | — (随机) | The headmaster awarded Emily the first prize in the English speech contest. |
| 3 | q_00453 | sentence_rewriting | — (随机) | The thief stole one million dollars'worth of gold from the store. |
| 4 | q_01004 | sentence_rewriting | — (随机) | The government made laws to prevent the wild environment from the pollution. |
| 5 | q_01003 | sentence_rewriting | — (随机) | In Switzerland，people sell some of the old clothes in charity shops. |

## 样例 8：三题型混合配额

- **用户诉求**：「4 道单选、3 道词性转换、3 道改写」
- **检索路径**：三桶配额分配 · SQL 随机
- **GenerateRequest**：`total_questions=10`<br>`question_types=[]`<br>`knowledge_points=[]`<br>`type_distribution={'single_choice': 4, 'word_form': 3, 'sentence_rewriting': 3}`<br>`free_text=''`
- **结果**：取到 10 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00786 | single_choice | — (随机) | Close your eyes and________you are sitting on a cloud.How do you feel？ |
| 2 | q_00637 | single_choice | — (随机) | ________quickly Lucy can do her work on the computer！ |
| 3 | q_00709 | single_choice | — (随机) | Because of the spread of the disease，our flight to France________last week. |
| 4 | q_00641 | single_choice | — (随机) | ________exciting form of dance Tap dancing is！ |
| 5 | q_00333 | word_form | — (随机) | On the way to________，you should push yourself hard and never give up. |
| 6 | q_00401 | word_form | — (随机) | —Which bird is the________in the world?—It might be the male white bell bird(白钟雀)of the Am |
| 7 | q_00297 | word_form | — (随机) | The boy could not sleep，and he began to count________，but failed. |
| 8 | q_00441 | sentence_rewriting | — (随机) | It is fun to enjoy the autumn leaves in Beijing. |
| 9 | q_00998 | sentence_rewriting | — (随机) | Our country sent a medical team to Italy two months ago. |
| 10 | q_00435 | sentence_rewriting | — (随机) | Kitty rarely went to bed after 11 o'clock. |

## 样例 9：关于科技的单选

- **用户诉求**：「来几道关于手机、网络、科技的单选」
- **检索路径**：向量语义检索 · RAG（另一主题，验证不止环保有效）
- **GenerateRequest**：`total_questions=5`<br>`question_types=['single_choice']`<br>`knowledge_points=[]`<br>`type_distribution={}`<br>`free_text='手机 网络 科技 technology internet'`
- **结果**：取到 5 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00789 | single_choice | 0.515 | We can get________information on the Net with the rapid development of science and technol |
| 2 | q_00061 | single_choice | 0.462 | A large number of________will be on sale on the Internet as promised. |
| 3 | q_00718 | single_choice | 0.442 | Mobile phones________in our daily life now，like making phone calls，paying and reading. |
| 4 | q_00634 | single_choice | 0.441 | The robot can serve customers in restaurants.________quickly the technology develops！ |
| 5 | q_00116 | single_choice | 0.439 | ________smooth the screen of your new smart phone feels! |

## 样例 10：介词 + 旅游主题

- **用户诉求**：「来 5 道跟旅游有关的介词单选」
- **检索路径**：KP 硬过滤 + 向量语义（两者同时生效）
- **GenerateRequest**：`total_questions=5`<br>`question_types=['single_choice']`<br>`knowledge_points=['kp_sc_prepositions']`<br>`type_distribution={}`<br>`free_text='关于旅游 出行 travel trip'`
- **结果**：取到 5 道

| # | id | 题型 | 相似度 | 内容预览 |
|---|----|------|-------|---------|
| 1 | q_00097 | single_choice | 0.460 | Many old Britons are still afraid to travel________the tunnel between England and France. |
| 2 | q_00623 | single_choice | 0.458 | More and more people go to work________public transport instead of driving private cars. |
| 3 | q_00090 | single_choice | 0.451 | —Excuse me，could you please tell me the way________the light rail station? |
| 4 | q_00096 | single_choice | 0.431 | Dear passengers，now you have 30 minutes to check________at Gate 30. |
| 5 | q_00628 | single_choice | 0.423 | It is impolite to make fun________disabled people. |

