"""
主题分类模块
===========
使用监督学习方法对评论数据进行主题分类，将每条评论归类到
五个预定义主题之一。使用自建标注数据集训练朴素贝叶斯分类器，
支持中英文混合文本的主题识别。

项目背景：针对美以伊战争（2026年2月28日爆发）的舆论分析

主题标签：
- 战争正义性 (War Justice): 关于战争是否正义、谁先挑起、合法性与道德性的讨论
- 战争影响 (War Impact): 关于经济影响、油价、全球安全、供应链等战争后果的讨论
- 各方评价 (Party Evaluation): 对美国、以色列、伊朗、中国、联合国等各方的评价
- 和平呼声 (Peace Calls): 呼吁和平、停火、外交解决方案的讨论
- 其他 (Other): 不属于以上任何类别的通用评论

分析流程：
1. 构建自建训练数据集（中英文各至少8-10条/类别）
2. 使用TF-IDF提取文本特征
3. 训练多项朴素贝叶斯分类器
4. 对评论数据进行主题预测
5. 输出分类结果和分布统计
"""

import os
import re
import pandas as pd
import numpy as np


def build_training_data():
    """
    构建自建训练数据集，包含中英文两种语言的标注样本。

    针对美以伊战争（2026年2月28日爆发）的舆论分析场景，
    每个类别包含中文和英文的典型评论，涵盖：
    - 战争正义性：正义性、合法性、道德性讨论
    - 战争影响：经济、油价、供应链等影响
    - 各方评价：对美国、以色列、伊朗、中国等各方评价
    - 和平呼声：停火、外交解决、和平呼吁
    - 其他：不属于以上类别的通用评论

    返回:
        list of str, 训练文本列表
        list of str, 对应的主题标签列表
    """
    # ========== 战争正义性 (War Justice) ==========
    texts_war_justice = [
        # 中文样本
        "美以对伊朗的军事打击缺乏国际法依据",
        "伊朗有权自卫反击外来侵略",
        "这场战争本质上是一场侵略战争",
        "美国绕过联合国发动袭击违背国际准则",
        "以色列对伊朗的先发制人打击是否合法值得商榷",
        "主权国家有权选择自己的发展道路他国无权干涉",
        "打着反恐旗号侵犯别国主权是霸权行径",
        "国际法明确规定不得对主权国家使用武力",
        "美以联军的军事行动没有得到安理会授权",
        "伊朗核计划是否构成威胁应由国际原子能机构认定",
        "美国以莫须有的罪名发动战争与伊拉克战争如出一辙",
        # 英文样本
        "This military strike against Iran violates international law",
        "Iran has the right to defend its sovereignty",
        "The US and Israel launched an illegal war of aggression",
        "Attacking Iran without UN authorization is a violation of the UN Charter",
        "The preemptive strike doctrine sets a dangerous precedent",
        "No country has the right to attack another based on unverified intelligence",
        "This is a clear case of great power bullying under false pretenses",
        "Iran's nuclear activities are within its sovereign rights",
    ]

    # ========== 战争影响 (War Impact) ==========
    texts_war_impact = [
        # 中文样本
        "油价飙升将导致全球经济衰退",
        "中东局势动荡影响一带一路建设",
        "战争导致全球供应链再次紧张",
        "海湾地区石油出口受阻推高能源价格",
        "霍尔木兹海峡航运安全受到严重威胁",
        "全球股市因中东战事大幅下挫",
        "战争引发的能源危机将重创欧洲经济",
        "航空业因中东空域关闭遭受重大损失",
        "粮食价格受能源价格上涨连动攀升",
        "战争推高通货膨胀各国央行面临两难",
        # 英文样本
        "Oil prices have surged due to the Middle East conflict",
        "The global economy faces another shock from this war",
        "Supply chains are disrupted again as the Strait of Hormuz is threatened",
        "Energy markets are in turmoil following the US-Israel strikes on Iran",
        "Stock markets worldwide plunged on news of the Iran attacks",
        "The war is causing ripple effects across global trade routes",
        "Shipping costs have skyrocketed due to Middle East instability",
        "Europe faces a severe energy crisis as Middle East supplies are cut",
    ]

    # ========== 各方评价 (Party Evaluation) ==========
    texts_party_eval = [
        # 中文样本
        "美国在中东的政策一贯是双重标准",
        "以色列在这次冲突中的角色值得警惕",
        "中国始终坚持劝和促谈的立场",
        "伊朗在面对外部压力时展现了韧性",
        "联合国在这场危机中的表现令人失望",
        "美国在中东的军事存在才是动荡的根源",
        "俄罗斯对美以军事行动表示强烈谴责",
        "欧洲国家在此次冲突中的立场分歧明显",
        "以色列借美国之力打压地区对手是惯用策略",
        "中国提出的中东安全倡议具有建设性",
        # 英文样本
        "The US double standard in the Middle East is evident",
        "Israel's role in this conflict needs scrutiny",
        "China's call for restraint shows responsible leadership",
        "The UN Security Council has failed to prevent this war",
        "Russia's condemnation of the strikes reflects growing multipolarity",
        "Iran has shown remarkable resilience under decades of sanctions",
        "European leaders are divided on how to respond to the crisis",
        "The US once again prioritizes military force over diplomacy",
    ]

    # ========== 和平呼声 (Peace Calls) ==========
    texts_peace_calls = [
        # 中文样本
        "希望各方尽快回到谈判桌前",
        "战争没有赢家和平没有输家",
        "国际社会应该加大斡旋力度",
        "停火是当前最紧迫的首要任务",
        "通过对话协商解决分歧才是正道",
        "武力只会带来更多的仇恨和对立",
        "中东经不起又一场大规模战争",
        "外交途径是解决伊朗核问题的唯一出路",
        "各方应保持克制避免局势进一步升级",
        "人类的理智应该战胜战争的冲动",
        # 英文样本
        "All parties must return to the negotiating table",
        "Peace is the only sustainable solution",
        "A ceasefire must be the immediate priority",
        "Diplomacy not bombs will resolve this crisis",
        "The world must unite to stop this senseless war",
        "Dialogue is the only path to lasting peace in the Middle East",
        "War will only breed more hatred and extremism",
        "We call on the international community to mediate an immediate truce",
    ]

    # ========== 其他 (Other) ==========
    texts_other = [
        # 中文样本
        "这件事让我想起了历史上的类似事件",
        "媒体报道的角度各不相同需要理性判断",
        "社交媒体上的信息真伪难辨",
        "每个人都有权表达自己的观点",
        "历史会给出公正的评价",
        "我们需要从多个角度看待这个问题",
        "信息的透明度对于公众判断至关重要",
        "不同文化背景的人对同一事件理解不同",
        "保持理性和冷静是当前最重要的",
        "网上关于这场战争的说法太多了不知道信谁",
        # 英文样本
        "This reminds me of similar events in history",
        "Media coverage varies widely depending on the source",
        "Social media information is hard to verify",
        "Everyone has the right to express their own opinion",
        "History will provide a fair judgment in time",
        "We need to look at this issue from multiple perspectives",
        "Information transparency is crucial for public understanding",
        "People from different cultures understand this conflict differently",
    ]

    # 汇总所有训练数据和对应的标签
    all_texts = []
    all_labels = []

    for text in texts_war_justice:
        all_texts.append(text)
        all_labels.append('战争正义性')

    for text in texts_war_impact:
        all_texts.append(text)
        all_labels.append('战争影响')

    for text in texts_party_eval:
        all_texts.append(text)
        all_labels.append('各方评价')

    for text in texts_peace_calls:
        all_texts.append(text)
        all_labels.append('和平呼声')

    for text in texts_other:
        all_texts.append(text)
        all_labels.append('其他')

    print(f"[训练数据] 共构建 {len(all_texts)} 条标注样本")
    label_counts = {label: all_labels.count(label) for label in set(all_labels)}
    for label, count in label_counts.items():
        print(f"  {label}: {count} 条")

    return all_texts, all_labels


def extract_features(texts):
    """
    使用TF-IDF向量化器提取文本特征。

    TF-IDF原理：
    - TF (Term Frequency): 词在文档中出现的频率
    - IDF (Inverse Document Frequency): 包含该词的文档比例的倒数对数
    - TF-IDF = TF × IDF，越高表示词对该文档越重要
    - max_features=5000: 限制特征维度，选取最重要的5000个词

    参数:
        texts: list of str, 文本列表

    返回:
        TfidfVectorizer, 训练好的向量化器
        scipy.sparse matrix, TF-IDF特征矩阵
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    # 创建TF-IDF向量化器
    # max_features=5000: 保留最重要的5000个特征词
    # max_df=0.9: 忽略出现在90%以上文档中的过于常见的词
    # min_df=1: 训练集较小，保留所有出现过的词
    # ngram_range=(1,2): 同时考虑单个词和双词组合（bigram）
    vectorizer = TfidfVectorizer(
        max_features=5000,
        max_df=0.9,
        min_df=1,
        ngram_range=(1, 2),
        token_pattern=r'(?u)\b\w+\b'
    )

    # 将文本转换为TF-IDF特征矩阵
    X = vectorizer.fit_transform(texts)

    print(f"[特征提取] TF-IDF特征维度: {X.shape[1]} 个特征词")
    return vectorizer, X


def train_model(X, y):
    """
    训练多项朴素贝叶斯（MultinomialNB）分类器。

    算法原理：
    - 多项朴素贝叶斯适用于离散特征（如词频/TF-IDF）
    - 假设特征之间条件独立（朴素假设）
    - 基于贝叶斯定理计算每个类别的后验概率
    - alpha=0.1: 拉普拉斯平滑参数，防止零概率问题

    参数:
        X: scipy.sparse matrix, TF-IDF特征矩阵
        y: list of str, 标签列表

    返回:
        MultinomialNB, 训练好的分类器模型
    """
    from sklearn.naive_bayes import MultinomialNB

    # 创建多项朴素贝叶斯分类器
    # alpha=0.1: 平滑参数，防止某些词在某些类别中概率为零导致整体概率为零
    model = MultinomialNB(alpha=0.1)

    # 训练模型
    model.fit(X, y)

    print(f"[模型训练] 多项朴素贝叶斯分类器训练完成")
    print(f"[模型训练] 类别数: {len(model.classes_)}")

    return model


def predict_topics(texts, model, vectorizer):
    """
    使用训练好的模型对新文本进行主题预测。

    参数:
        texts: list of str, 待分类的文本列表
        model: MultinomialNB, 训练好的分类器
        vectorizer: TfidfVectorizer, 训练好的向量化器

    返回:
        list of tuples, [(主题标签, 置信度概率), ...]
    """
    # 将文本转换为TF-IDF特征
    X_new = vectorizer.transform(texts)

    # 获取各类别的预测概率
    proba = model.predict_proba(X_new)

    # 获取预测标签
    predictions = model.predict(X_new)

    # 组合标签和最大置信度
    results = []
    for i, pred in enumerate(predictions):
        # 获取该预测类别的置信度（概率）
        # proba是按model.classes_顺序排列的，需要找到pred对应的索引
        class_idx = list(model.classes_).index(pred)
        confidence = float(proba[i][class_idx])
        results.append((pred, confidence))

    return results


def classify_topics(df, model_path=None):
    """
    主题分类的主函数，完成从训练到预测的完整流程。

    处理流程：
    1. 构建训练数据集
    2. 提取TF-IDF特征
    3. 训练朴素贝叶斯分类器
    4. 对DataFrame中的评论进行预测
    5. 可选保存训练好的模型

    参数:
        df: pd.DataFrame, 包含'content'列的评论数据
        model_path: str or None, 模型保存路径（None表示不保存）

    返回:
        pd.DataFrame, 添加了'topic_label'和'topic_confidence'列的数据框
    """
    # 第一步：构建训练数据
    train_texts, train_labels = build_training_data()

    # 第二步：提取特征
    vectorizer, X_train = extract_features(train_texts)

    # 第三步：训练模型
    model = train_model(X_train, train_labels)

    # 第四步：对DataFrame中的评论进行预测
    # 提取有效文本内容（过滤空值）
    contents = []
    valid_indices = []

    for idx, row in df.iterrows():
        content = row.get('content', '')
        if isinstance(content, str) and content.strip():
            contents.append(content)
            valid_indices.append(idx)

    if not contents:
        print("[警告] 没有有效的文本内容可用于分类")
        df['topic_label'] = '其他'
        df['topic_confidence'] = 0.0
        return df

    print(f"[主题预测] 正在对 {len(contents)} 条评论进行分类...")
    predictions = predict_topics(contents, model, vectorizer)

    # 初始化结果列
    df['topic_label'] = '其他'
    df['topic_confidence'] = 0.0

    # 填入预测结果
    for i, idx in enumerate(valid_indices):
        label, confidence = predictions[i]
        df.at[idx, 'topic_label'] = label
        df.at[idx, 'topic_confidence'] = round(confidence, 4)

    # 统计分类分布
    label_counts = df['topic_label'].value_counts()
    total = len(df)
    print(f"\n[主题分类] 分类完成! 共 {total} 条数据")
    for label in ['战争正义性', '战争影响', '各方评价', '和平呼声', '其他']:
        count = label_counts.get(label, 0)
        pct = count / total * 100 if total > 0 else 0
        print(f"  {label}: {count} 条 ({pct:.1f}%)")

    # 可选：保存模型
    if model_path:
        try:
            import joblib
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            joblib.dump({'model': model, 'vectorizer': vectorizer}, model_path)
            print(f"[模型保存] 分类模型已保存至: {model_path}")
        except ImportError:
            print("[警告] joblib未安装，无法保存模型。请执行: pip install joblib")
        except Exception as e:
            print(f"[警告] 模型保存失败: {e}")

    return df


def main():
    """
    主题分类模块入口函数。

    优先从 data/processed/sentiment_results.csv 读取数据（保留情感分析结果），
    如不存在则回退到 data/processed/clean_data.csv 或 data/sample/ 示例数据。
    训练朴素贝叶斯分类器，对评论进行主题分类，
    结果保存到 data/processed/topic_results.csv。
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(base_dir, "data", "processed")

    # 优先读取情感分析结果（如果存在），否则回退到清洗数据或示例数据
    input_path = os.path.join(base_dir, "data", "processed", "sentiment_results.csv")
    if not os.path.exists(input_path):
        input_path = os.path.join(base_dir, "data", "processed", "clean_data.csv")
    if not os.path.exists(input_path):
        print(f"[警告] 找不到已处理的数据文件")
        print("[提示] 请先运行 clean_data.py 或 sentiment_analysis.py")
        # 回退到示例数据
        sample_path = os.path.join(base_dir, "data", "sample", "sample_comments.csv")
        if os.path.exists(sample_path):
            print(f"[回退] 将使用示例数据: {sample_path}")
            input_path = sample_path
        else:
            return

    output_path = os.path.join(output_dir, "topic_results.csv")
    model_path = os.path.join(output_dir, "topic_classifier.joblib")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    try:
        print(f"[读取] 正在读取数据: {input_path}")
        df = pd.read_csv(input_path, encoding='utf-8')
        print(f"[读取] 共 {len(df)} 条数据\n")

        # 执行主题分类
        df = classify_topics(df, model_path=model_path)

        # 保存结果
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n[保存] 主题分类结果已保存至: {output_path}")

    except Exception as e:
        print(f"[错误] 主题分类过程中发生异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
