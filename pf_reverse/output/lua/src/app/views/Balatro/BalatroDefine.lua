local P = {}
Bal = P

--盲注类型
P.BlindType = 
{
    Normal = 1, --普通
    Elite = 2, --精英
    Boss = 3, --Boss
}

--通过盲注类型
P.ClearBlindsType = {
    Clear = 1, --通关
    Pass = 2, --跳过
}

--牌型
P.CardType = 
{
    HighCard = 1, --高牌
    Pair = 2, --对子
    TwoPair = 3, --两对
    ThreeKind = 4, --三条
    Straight = 5, --顺子
    Flush = 6, --同花
    FullHouse = 7, --葫芦
    FourKind = 8, --四条
    StraightFlush = 9, --同花顺
    RoyalFlush = 10, --皇家同花顺

    --暂不开放
    FiveKind = 11, --五条
    FullHouseFlush = 12, --同花葫芦
    FiveKindFlush = 13, --同花五条
}

--牌型包含关系
P.CardTypeIncludeDic = {
    [P.CardType.HighCard] = {},
    [P.CardType.Pair] = {P.CardType.Pair},
    [P.CardType.TwoPair] = {P.CardType.TwoPair, P.CardType.Pair},
    [P.CardType.ThreeKind] = {P.CardType.ThreeKind, P.CardType.Pair},
    [P.CardType.Straight] = {P.CardType.Straight},
    [P.CardType.Flush] = {P.CardType.Flush},
    [P.CardType.FullHouse] = {P.CardType.FullHouse, P.CardType.ThreeKind, P.CardType.TwoPair, P.CardType.Pair},
    [P.CardType.FourKind] = {P.CardType.FourKind, P.CardType.ThreeKind, P.CardType.Pair},
    [P.CardType.StraightFlush] = {P.CardType.StraightFlush, P.CardType.Flush, P.CardType.Straight},
    [P.CardType.RoyalFlush] = {P.CardType.RoyalFlush, P.CardType.StraightFlush, P.CardType.Flush, P.CardType.Straight},
    [P.CardType.FiveKind] = {P.CardType.FiveKind, P.CardType.FourKind, P.CardType.ThreeKind, P.CardType.Pair},
    [P.CardType.FullHouseFlush] = {P.CardType.FullHouseFlush, P.CardType.Flush, P.CardType.FullHouse, P.CardType.ThreeKind, P.CardType.TwoPair, P.CardType.Pair},
    [P.CardType.FiveKindFlush] = {P.CardType.FiveKindFlush, P.CardType.Flush, P.CardType.FiveKind, P.CardType.FourKind, P.CardType.ThreeKind, P.CardType.Pair},
}

--花色
P.PokerSuit = 
{
    Diamond = 1, --方块
    Club = 2, --梅花
    Heart = 3, --红桃
    Spade = 4, --黑桃
}
--数值
P.PokerValue = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
P.PokerScore = {14, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
--Ace牌
P.PokerAceType = {1}
--数值牌
P.PokerNumberType = {2, 3, 4, 5, 6, 7, 8, 9, 10}
--人头牌
P.PokerHumanType = {11, 12, 13}
--非人头牌
P.PokerUnHumanType = {1, 2, 3, 4, 5, 6, 7, 8, 9}
--斐波那契
P.FibonacciType = {1, 2, 3, 5, 8}
--偶数
P.EvenNumberType = {2, 4, 6, 8, 10}
--奇数
P.OddNumberType = {1, 3, 5, 7, 9}
--小额数
P.SmallNumberType = {2, 3, 4, 5}

--扑克点数类型
P.PokerPointType = 
{
    Human = 1, --人头牌
    Number = 2, --数值牌
    Ace = 3, --Ace牌
}

--指定卡组内包含类型
P.DesCardInGroupType =
{
    Point = 1, --点数
    Enhance = 2, --强化
}

--同数值的类型
P.PokerSameValueType = 
{
    One = 1, 
    Two = 2,
    Three = 3,
    Four = 4,
    Five = 5,
}

--顺子类型
P.PokerStraightType = 
{
    None = 0,
    Normal = 1, --普通
    Royal = 2, --皇家
}
--皇家顺子
P.RoyalFlushValue = {10, 11, 12, 13, 1}

--扑克排序类型
P.PokerSortType = 
{
    Point = 1, --大小
    Suit = 2, --花色
}

--等式类型
P.EquationType =
{
    Greater = 1, --大于
    Less = 2, --小于
    Equal = 3, --等于
    GreaterOrEqual = 4, --大于等于
    LessOrEqual = 5, --小于等于
}

--选择盲注类型
P.SelectBlindType =
{
    All = 1, --所有盲注
    BS = 2, --大小盲注
    Boss = 3, --Boss盲注
}

--回收扑克类型
P.RecoveryPokerType = 
{
    Played = 1, --出牌回收
    Fold = 2, --弃牌
    Reall = 3, --回收全部
    BossSkill = 4, --Boss技能
    NotAllow = 5, --不允许
}

--参数类型
P.ParameterType =
{
    Chip = 1, --筹码
    Power = 2, --倍率
    MulPower = 3, --倍乘
    HandCard = 4, --手牌上限
    Gold = 5, --金币
    StrengthenCard = 6, --随机强化卡
    JokerCard = 7, --随机小丑牌
    TarotCard = 8, --随机塔罗牌
    SpectralCard = 9, --随机幻灵牌 
    PlayCount = 10, --出牌次数
    FoldCount = 11, --弃牌次数
    PlanetCard = 13, --星球牌

    -- CardType = 50, --牌型

    -- Again = 101, --再来一次
    -- Nothing = 102, --没有
    -- Rerun = 103, --重算
    -- Change = 104, --变动
    -- Safe = 105, --安全

    -- Destroy = 201, --销毁
}

--卡牌种类
P.CardCategory =
{
    None = 0,
    Joker = 1, --鬼牌
    Planet = 2, --星球
    Tarot = 3, --塔罗
    Spectral = 4, --幻灵
    Vouchers = 5, --优惠券
    Package = 7, --补充包
    Poker = 99, --扑克
}

--强化类型
P.CardStrengthenType = 
{
    Enhance = 1, --增强
    Edition = 2, --版本
    Seal = 3, --蜡封
}

--版本类型
P.EditionType =
{
    Base = 101, --基础
    Foil = 102, --闪卡 筹码+50
    Holographic = 103, --镭射 倍率+10
    Polychrome = 104, --多彩 倍率*1.5
    Negative = 105, --负片 鬼牌槽位+1
}

--增强类型
P.EnhanceType = 
{
    Bonus = 1, --奖励 筹码+30
    Mult = 2, --倍率 倍率+4
    Wild = 3, --万能
    Glass = 4, --玻璃 倍率*2 1/4计分后摧毁
    Steel = 5, --钢铁 倍率*1.5 留在手牌时
    Stone = 6, --石头 筹码+50
    Gold = 7, --金卡 获得3元 回合结束时留在手牌
    Lucky = 8, --幸运 1/5概率倍率+20 1/15概率获得20元
}

--封蜡类型
P.SealType =
{
    Gold = 201, --金 打出后计分获得3元
    Red = 202, --红 重新触发卡牌
    Blue = 203, --蓝 生成最后一个出手牌型的星球牌
    Purple = 204, --紫 被弃牌时生成一张塔罗牌
}

--补充包类型
P.SupplementPackageType = 
{
    Joker = 1, --鬼牌包
    Planet = 2, --天体包
    Tarot = 3, --塔罗包
    Spectral = 4, --幻灵包
    Poker = 5, --扑克包
}

--商店出现的卡牌种类
P.ShopCardCategory = 
{
    Joker = 101, --鬼牌
    Planet = 102, --天体牌
    Tarot = 103, --塔罗牌
    Spectral = 104, --幻灵牌
    Poker = 105, --扑克牌
}

--鬼牌品质
P.JokerQualityType = 
{
    Normal = 1, --普通
    Rare = 2, --罕见 
    Unusual = 3, --稀有 
    Legend = 4, --传奇
    Random = 99,
}

--效果触发时机
P.EffectTriggerType = 
{
    SelectBlind = 1, --选择盲注
    PassBlind = 20, --跳过盲注
    RoundStart = 2, --回合开始
    Play = 19, --出牌
    Fold = 3, --弃牌

    ConfirmCard = 4, --确认出牌
    PokerScoring = 5, --出牌计分
    HandCardScoring = 6, --手牌计分
    JokerScoring = 7, --鬼牌计分
    ConsumeCardScoring = 8, --消耗牌计分

    ScoringOver = 9, --计分结束
    RoundOver = 10, --回合结束
    EnterShop = 11, --进入商店
    RefreshShop = 12, --刷新商店
    LeaveShop = 13, --离开商店
    Passive = 14, --被动 选择卡牌后立即触发
    SellCard = 15, --卡牌出售
    OpenPackage = 16, --打开补充包
    PassPackage = 17, --跳过补充包

    RightNow = 18, --立即触发
    ClearBoss = 21, --击败boss
    PlayEveryPoker = 22, --每次打出扑克
}

--鬼牌效果变动时间点
P.JokerEffectChangePoint = 
{
    JokerCountChange = 1, --鬼牌数量变动
    JokerCostChange = 2, --鬼牌价格变动 x
    SellCard = 3, --出售卡牌

    SelectBlind = 4, --选择盲注（大小盲注、Boss盲注、所有）
    PassBlind = 5, --跳过盲注
    
    PlayCard = 6, --出牌时
    Scoring = 7, --得分时
    ScoringOver = 8, --出牌计分结束
    FoldCard = 9, --弃牌时
    PlayAndFoldCard = 10, --出牌弃牌
    RoundOver = 11, --回合结束

    GroupChange = 12, --卡组总数变动
    GroupRemainChange = 18, --卡组剩余数量变动
    StrengthenPokerChange = 19, --强化卡牌变动

    CurrencyChange = 13, --货币变动
    UsedConsumeCard = 14, --使用消耗卡（星球卡、塔罗牌
    RefreshShop = 15, --刷新商店
    PassPackage = 16, --跳过补充包
    DestroyCard = 17, --摧毁卡牌
}

--表现阶段
P.DisplayType = {
    RoundStart = 1, --回合开始
    RoundOver = 2, --回合结束
    GetJoker = 3, --获得鬼牌
    RemoveJoker = 4, --移除鬼牌
    GetPoker = 5, --获得扑克
    FoldPoker = 6, --弃牌
    RemovePoker = 7, --移除扑克
    Scoring = 8, --计分

    SelectBlind = 9, --选择盲注
    PassBlind = 10, --跳过盲注
    RefreshShop = 11, --刷新商店
}

--筹码颜色
P.ChipColor = '#00D0FF'
--倍率颜色
P.PowerColor = '#FF5353'

--卡牌所在类型
P.CardPlaceType = 
{
    None = 0,
    Slot = 1, --卡槽
    Shop = 2, --商店
    Supplement = 3, --补充包
}

--槽位类型
P.SoltType = 
{
    Shop = 1, --商店牌区
    Consume = 2, --消耗牌区
    Joker = 3, --鬼牌区
}

--发牌类型
P.DealCardType = 
{
    Deal = 1, --发牌
    Replenish = 2, --补牌
    Other = 3, --其他
    Replenish_Play = 4, --补牌_出牌
    Replenish_Fold = 5, --补牌_弃牌
}

--消耗牌使用类型
P.ConsumeUseType = 
{
    Direct = 1, --直接使用
    InPoker = 2, --扑克之上
}

--战局进度状态
P.BattleProgressStatus = {
    SelectBlind = 1, --选择盲注
    PlayCard = 2, --出牌
    Shop = 3, --商店
    Settlement = 4, --结算
}

--战斗结果
P.BattleResultType = {
    None = 0,
    Win = 1,
    Lose = 2,
}

--盲注效果类型
P.BlindEffectType = 
{
    EveryPlayedFoldCard = 1, --出牌后弃牌
    PlayCommonCardTypeClearCurrency = 2, --打出常用牌型时，资金归零
    BackCardInFirstDealHandCard = 3, --首次抽牌时背面朝上
    BackCardRatioByDrawCard = 4, --抽卡概率抽到背面朝上的卡
    DownPlayedCardType = 5, --降低打出的牌型等级
    WeakenSuit = 6, --削弱花色
    BackCardByDrawCard = 7, --补牌背面朝上
    NeedPlayAppointCount = 8, --必须出规定数量
    ChangeFoldCount = 9, --弃牌数变化
    ChangeKeepCardCount = 10, --手牌上限变化
    CardTypeLimitation = 11, --牌型限制
    HumanCardLimitation = 12, --人头牌限制
    FixDrawCardCount = 13, --固定抽牌张数
    WeakenCurAntePlayedCard = 14, --出过的牌都被削弱
    FixPlayCount = 15, --固定出牌次数
    LossCurrencyEveryPlayedCard = 16, --每出一张牌失去资金
    HalveChipAndPower = 17, --筹码倍率减半
    RandomJokerIndex = 18, --随机小丑牌位置
    WeakenAllCard = 19, --削弱所有卡牌
    LoseEffectJoker = 20, --小丑牌失效
    ForceSelectPoker = 21, --强制选中扑克
}

--默认持牌数量
P.DefaultKeepCount = 7
--默认鬼牌数量
P.DefaultJokerCount = 8
--默认货币数量
P.DefaultCurrency = 5
--默认出牌次数
P.DefaultPlayCount = 4
--默认弃牌次数
P.DefaultFoldCount = 3


--发牌间隔
P.DealInterval = 0.1
--卡牌动效持续时间
P.CardEffectKeepTime = 0.6
--卡牌动效持续时间
P.CardEffectKeepEffTime = 1
--出牌展示时间
P.PlayPokerTime = 0.14
--回收卡牌时间
P.RecoveryPokerTime = 0.1
--生成新卡牌时间
P.CreateNewCardTime = 0.5

return P