local P = class("BalBattleModel", BaseModel)
BalBattleModel = P

function P:ctor(logic)
    --递增唯一id
    self.addtUid = 0
    --战斗种子
    self.battleSeed = 0
    --随机序列号
    self.randomIndex = 0
    --缓存随机序列
    self.cacheRandomIndex = 0
    --对局中
    self.playing = false

    --默认牌组数据 52张基础卡牌
    self.defaultPokerDataDic = {}
    --对局牌组数据
    self.matchingPokerDataDic = {}
    --当前对局卡牌剩余列表
    self.matchingRemainIdList = {}
    --当局可用扑克牌
    self.usablePokerCardData = {}
    --排序类型
    self.sortType = 0

    --当前手中卡牌数据
    self.displayPokerList = {}
    --当前回合打出的卡牌数据
    self.playedPokerList = {}
    --拥有的鬼牌数据
    self.ownedJokerList = {}
    --可拥有的鬼牌上限
    self.maxJokerSlot = 0

    --选中的卡牌数据
    self.selectingCardDic = {}
    --当前可持牌数量
    self.matchingKeepCardCount = 0
    --额外可持牌数量
    self.extraKeepCardCount = 0
    --可出牌次数
    self.playableCount = 0
    --可弃牌次数
    self.foldableCount = 0
    --已出牌次数
    self.playedCount = 0
    --已弃牌次数
    self.foldedCount = 0
    --缓存出牌次数
    -- cachePlayCount = 0
    --缓存弃牌次数
    -- cacheFoldCount = 0

    --固定补牌数量
    self.fixDrawCardCount = 0
    --鬼牌的剩余随机数量
    self.jokerRefreshRemain = 0

    --当前关卡
    self.curLevel = 0
    --本次出牌得分牌列表
    self.curScoringList = nil
    --当前对局牌型等级
    self.cardTypeLv = {}
    --当前牌型
    self.curCardType = nil
    --牌型养成数据
    self.cardTypeGrowthData = {}  -- [B.CardType.HighCard] = {chip = 10, chipUp = 10, power = 1, powerUp = 1}
    --当前筹码
    self.curChip = 0
    --当前倍率
    self.curPower = 0

    --无尽已通关次数
    self.endlessTime = 0

    --减半基础筹码倍率
    self.halveBaseChipPower = 1
    --目标分数
    self.targetScore = 0
    --当前分数
    self.matchingScore = 0
    --胜负
    self.battleResult = 0

    --当前持有货币
    self.matchingCurrency = 0
    --底注回合
    self.anteRound = 1

    --通过的盲注数据
    self.clearBlindsData = {}
    --使用过的卡牌记录
    self.usedPokerIds = {}
    --打出的牌型记录
    self.playedCardTypeData = {}
    --本回合打出的牌型记录
    self.playedCardTypeInRoundData = {}
    --本回合得分牌记录
    self.getScorePokerInRoundData = {}
    --本底注得分牌记录
    self.getScorePokerInAnteData = {}
    --累计出牌次数
    self.totalPlayCount = 0
    --累计剩余弃牌数量
    self.totalRemainFoldCount = 0
    --累计跳过盲注次数
    self.totalPassBlindCount = 0
    --行为数据
    self.operationDataList = {}

    --强制选中
    self.forceSelectId = nil
    
    --装饰方案
    self.scheme = nil

    P.super.ctor(self)
end


function P:initRequire()
    require "app.views.Balatro.BalatroDefine"
    require "app.views.Balatro.BalatroRule"
    require "app.views.Balatro.BalSkillUtil"
    require "app.views.Balatro.JokerUtil"
    require "app.views.Balatro.PokerUtil"
    require "app.views.Balatro.BaseCardUtil"

    self.sortType = Bal.PokerSortType.Point
    self.maxJokerSlot = table.nums(tpl_fate_seat)
end

--获取唯一id
function P:getNewUid()
    self.addtUid = self.addtUid + 1
    return self.addtUid 
end

--创建随机数生成器
function P:CreateBattleRandom(seed)
    self.battleSeed = seed ~= 0 and seed or os.time()
    self.random = CS.System.Random(self.battleSeed)
    if self.randomIndex > 0 then
        local randomCount = self.randomIndex
        self.randomIndex = 0
        for i = 1, randomCount do
            self:GetRandom(0, 1)
        end
    end
end
--获取战斗随机正整数[s, e)
function P:GetRandom(s, e)
    self.randomIndex = self.randomIndex + 1
    return self.random:Next(s, e)
end

--#region 流程

--初始化对局
function P:initBattleData()
    self.operationDataList = {}
    self.battleSeed = os.time()
    self:CreateBattleRandom(self.battleSeed)
    --牌组
    self.defaultPokerDataDic = PokerUtil:createDefaultPokerGroupData()
    self.matchingPokerDataDic = clone(self.defaultPokerDataDic)
    self.matchingRemainIdList = {}
    for _,v in pairs(self.matchingPokerDataDic) do
        table.insert(self.matchingRemainIdList, v.uid)
    end
    self.usablePokerCardData = clone(self.defaultPokerDataDic)

    --手牌
    self.matchingKeepCardCount = Bal.DefaultKeepCount
    self.displayPokerList = {}
    self.selectingCardDic = {}

    --筹码 倍率 分数
    self:resetScore()

    --货币 鬼牌
    -- self.matchingCurrency = B.DefaultCurrency
    -- self.maxJokerSlot = B.DefaultJokerCount
    
    --出牌 弃牌
    local lvCfg = tpl_fate_main_level[self.curLevel]
    self.playableCount = lvCfg.chance or Bal.DefaultPlayCount
    self.foldableCount = lvCfg.change or Bal.DefaultFoldCount
    self.playedCount = 0
    self.foldedCount = 0

    --统计数据
    self.playedCardTypeData = {}
    self.playedCardTypeInRoundData = {}
    self.totalPlayCount = 0
end

--回合开始
function P:roundStart()
    --对局方案
    self.scheme = DecorationModel:getInGameCurScheme()

    --设置目标分数
    local lvCfg = tpl_fate_main_level[self.curLevel]
    self.targetScore = lvCfg.score or 0

    --发牌
    self:dealPoker()
    -- local pokerDatas = self:dealPoker()
    -- bee.emit("evt_BalDealPoker", pokerDatas)

    BalSkillUtil:roundStart(self.ownedJokerList)
end

--新的一手
function P:newHand()
    --补牌
    local pokerDatas = self:replenishPoker()
    bee.emit("evt_BalReplenishPoker", pokerDatas)
end

--下一手判定/结束判定
function P:checkGameOver()
    local gameOver = false
    --胜利
    if self.targetScore <= self.matchingScore then
        gameOver = true
    end
    --失败
    if self:getRemainPlayCount() <= 0 then
        gameOver = true
    end
    return gameOver
end

-- function P:checkToNext()
--     local gameOver = self:checkGameOver()
--     if gameOver then
--         self:gameOver()
--     end
--     return not gameOver
-- end


--#endregion

--#region 鬼牌

--获得鬼牌
function P:getJoker(cardData)
    -- BaseCardUtil:resetCardState(card)

    table.insert(self.ownedJokerList, cardData)
    -- card.index = table.nums(self.ownedJokerList)
end

--出售鬼牌
function P:sellJoker(card, cost)
    for k,v in pairs(self.ownedJokerList) do
        if v.uid == card.uid then
            -- BaseCardUtil:recoveryCard(card)
            table.remove(self.ownedJokerList, k)
        end
    end

    self:resortJokerIndex()
    
end

--重新排序鬼牌
function P:resortJokerIndex()
    -- for k,v in pairs(self.ownedJokerList) do
    --     v.index = k
    -- end
end

--交换鬼牌
function P:exchangeJoker(uid, index)
    for k,v in pairs(self.ownedJokerList) do
        if v.uid == uid then
            local jokerData = v
            table.remove(self.ownedJokerList, k)
            table.insert(self.ownedJokerList, index, jokerData)
        end
    end
end

--鬼牌数量是否达到上限
function P:checkJokerMax()
    return table.nums(self.ownedJokerList) >= self.maxJokerSlot
end

--#endregion

--#region 扑克

--新增扑克
function P:AddNewPoker(pokerData, addInGroup)
    self.matchingPokerDataDic[pokerData.uid] = pokerData
    if addInGroup then
        table.insert(self.matchingRemainIdList, pokerData.uid)
    end
end

--删除扑克
function P:DestroyPoker(pokerData)
    self.matchingPokerDataDic[pokerData.uid] = nil
    for k,v in pairs(self.matchingRemainIdList) do
        if v == pokerData.uid then
            table.remove(self.matchingRemainIdList, k)
            break
        end
    end
    --如果是选中的手牌
    if self.selectingCardDic[pokerData.uid] ~= nil then
        self.selectingCardDic[pokerData.uid] = nil
    end
end

--发牌
function P:dealPoker()
    local pokerDatas = {}
    for i = 1, self.matchingKeepCardCount do
        local data = PokerUtil:getPokerData()
        if data == nil then
            --扑克数量不足
            break
        end
        table.insert(pokerDatas, data)
        table.insert(self.displayPokerList, data)
    end
    return pokerDatas
end

--补牌
function P:replenishPoker()
    local curCount = table.nums(self.displayPokerList)
    local disCount = self.fixDrawCardCount ~= 0 and self.fixDrawCardCount or (self.matchingKeepCardCount - curCount)
    local pokerDatas = {}
    for i = 1, disCount do
        local data = PokerUtil:getPokerData()
        if data == nil then
            --扑克数量不足
            break
        end
        table.insert(pokerDatas, data)
        table.insert(self.displayPokerList, data)
    end
    return pokerDatas
end

--弃牌
function P:foldCard()
    self:changeFoldedCount()
end

function P:foldPoker(id)
    return self:removeDisplayPoker(id)
end

function P:removeDisplayPoker(id)
    local pokerData = nil
    for k,v in pairs(self.displayPokerList) do
        if v.uid == id then
            pokerData = v
            table.remove(self.displayPokerList, k)
            break
        end
    end
    return pokerData
end

--出牌
function P:playCard()
    self:changePlayedCount()

    local data = BalatroRule:CheckCardType(self.selectingCardDic)
    self.curScoringList = data and data.cardList or {}
    self.curCardType = data and data.type or nil
    self.totalPlayCount = self.totalPlayCount + 1
    --牌型统计
    if self.playedCardTypeData[self.curCardType] == nil then
        self.playedCardTypeData[self.curCardType] = 0
    end
    self.playedCardTypeData[self.curCardType] = self.playedCardTypeData[self.curCardType] + 1
    --当前回合牌型统计
    if self.playedCardTypeInRoundData[self.curCardType] == nil then
        self.playedCardTypeInRoundData[self.curCardType] = 0
    end
    self.playedCardTypeInRoundData[self.curCardType] = self.playedCardTypeInRoundData[self.curCardType] + 1
end

--清空手牌
function P:clearSelectingCardDic()
    self.selectingCardDic = {}
end

--#endregion

--#region 版本，强化，蜡封

--获得随机强化
function P:GetRandomEnhance()
    --  local etype = self:getRandomProbability(SkillManager.enhanceProbability)
    return nil
end

--获得随机蜡封
function P:GetRandomSeal()
    -- local stype = self:GetRandomProbability(SkillManager.sealProbability)
    return nil
end

--#endregion

--#region 筹码倍率

function P:setChipAndPower(cardType)
    if cardType == nil then
        self:resetScore()
        return
    end

    local lvCfg = self:getCardTypeLvId(cardType)
    self.curChip = lvCfg.scores
    self.curPower = lvCfg.multiple
    -- bee.emit("evt_refreshChipAndPower")
end

--重置筹码倍率
function P:resetScore()
    self.curChip = 0
    self.curPower = 0
    -- bee.emit("evt_refreshChipAndPower")
end

--获取牌型等级对应id
function P:getCardTypeLvId(cardType, lv)
    if lv == nil then
        lv = self.cardTypeLv[cardType]
    end
    local typeLvId = tonumber(cardType .. string.format("%03d", lv))
    local lvCfg = tpl_fate_card_level[typeLvId]
    return lvCfg
end

--#endregion

--#region 货币

--货币变动
function P:changeCurrency(value)
    if value == nil or value == 0 then return end

    self.matchingCurrency = self.matchingCurrency + value
    --鬼牌效果变动 货币变动
    BalSkillUtil:checkJokerEffectChange(Bal.JokerEffectChangePoint.CurrencyChange)
    --刷新货币
    -- bee.emit("evt_BRefreshCurrencySignal", {value = value})
end

--货币判定是否足够
function P:checkCurrencySufficient(value)
    return self.matchingCurrency >= value
end

--#endregion

--#region 手牌数量、 出牌次数、 弃牌次数

--判定并变动常态参数值
function P:changeParameterCount(type, num)
    if type == Bal.ParameterType.HandCard then
        self:changeHandCardCount(num)
    elseif type == Bal.ParameterType.PlayCount then
        self:changeMatchingPlayCount(num)
    elseif type == Bal.ParameterType.FoldCount then
        self:changeMatchingFoldCount(num)
    end
end

--手牌数量变动
function P:changeHandCardCount(num)
    self.matchingKeepCardCount = self.matchingKeepCardCount + num
    -- bee.emit("")
end
--可出牌次数变动
function P:changeMatchingPlayCount(num)
    self.playableCount = self.playableCount + num
    self.playableCount = math.max(0, self.playableCount)
    -- bee.emit("")
end
--可弃牌次数变动
function P:changeMatchingFoldCount(num)
    self.foldableCount = self.foldableCount + num
    self.foldableCount = math.max(0, self.foldableCount)
    -- bee.emit("")
end
--已出牌次数变动
function P:changePlayedCount(num)
    self.playedCount = self.playedCount + (num or 1)
end
--已弃牌次数变动
function P:changeFoldedCount(num)
    self.foldedCount = self.foldedCount + (num or 1)
end

--获取剩余出牌次数
function P:getRemainPlayCount()
    return self.playableCount - self.playedCount
end
--获取剩余弃牌次数
function P:getRemainFoldCount()
    return self.foldableCount - self.foldedCount
end


--#endregion

--#region 网络

--请求玩法数据
function P:getClownInfo()
    self.addtUid = 0
    Net:sendReq("pb.GetClownInfoREQ", {})
end
function P:evt_GetClownInfoRSP(msg)
    self.curLevel = msg.level
    self.ownedJokerList = {}
    for _,v in pairs(msg.seat_cards) do
        self:setOwnedJokerData(v)
    end

    self:setCardTypeLv()
    self.jokerRefreshRemain = msg.refresh
    self.endlessTime = msg.endless_times or 0
    bee.emit("evt_refreshBalatroData")
end

--刷新鬼牌
function P:refreshJokerCard(seatId)
    Net:sendReq("pb.RefreshSeatCardREQ", {seat = seatId})
end
function P:evt_RefreshSeatCardRSP(msg)
    if msg.code ~= 0 then
        return
    end
    self.jokerRefreshRemain = tpl_constdata.Refresh_Count - msg.refresh
    for _,v in pairs(msg.seat_cards) do
        self:setOwnedJokerData(v)
    end
    bee.emit("evt_refreshJokerData", msg.seat)
end

--鬼牌位置变动
function P:changeJokerSeat()
    local args = {}
    args.card_player_ids = {}
    for _,v in pairs(self.ownedJokerList) do
        table.insert(args.card_player_ids, v.skillId)
    end
    Net:sendReq("pb.CardPlayerSeatChangeREQ", args)
end

--设置牌型等级
function P:setCardTypeLv()
    for _,v in pairs(tpl_fate_card_type) do
        self.cardTypeLv[v.id] = 1
    end
    
    for _,v in pairs(tpl_fate_main_level) do
        if v.id < self.curLevel then
            self.cardTypeLv[v.upgrade[1]] = self.cardTypeLv[v.upgrade[1]] + v.upgrade[2]
        end
    end
end
function P:cardTypeLvUp()
    local cfg = tpl_fate_main_level[self.curLevel]
    if cfg then
        self.cardTypeLv[cfg.upgrade[1]] = self.cardTypeLv[cfg.upgrade[1]] + cfg.upgrade[2]
    end
end

--开始挑战
function P:startChallenge()
    Net:sendReq("pb.StartChallengeREQ", {})
end
function P:evt_StartChallengeRSP(msg)
    if msg.code ~= 0 then
        return
    end

    self.playing = true
    self.curLevel = msg.level
    self.battleSeed = msg.rand_seed
    for _,v in pairs(msg.seat_cards) do
        self:setOwnedJokerData(v)
    end
    self.targetScore = tpl_fate_main_level[self.curLevel].score
    self.matchingScore = 0
    bee.emit("evt_balatroGameStart")
end

function P:setOwnedJokerData(data)
    if data.id <= 0 then
        return
    end
    local jokerData = JokerUtil:creatNewJokerData()
    jokerData.uid = self:getNewUid()
    jokerData.skillId = data.id
    jokerData.skillParams.accCount = data.count or 0
    self.ownedJokerList[data.seat] = jokerData

    BalSkillUtil:initJokerEffect(jokerData)
end

--数据整理
function P:sortOutCtrlData(op)
    local data = {}
    data.op = op
    data.cards = {}
    for _,v in pairs(self.displayPokerList) do
        table.insert(data.cards, v.pid)
    end
    data.op_cards = {}
    for _,v in pairs(self.selectingCardDic) do
        table.insert(data.op_cards, v.pid)
    end
    if op == 1 then
        data.card_type = self.curCardType
        local lvCfg = self:getCardTypeLvId(self.curCardType)
        data.card_type_lv = lvCfg.id
    end
    data.play_times = self:getRemainPlayCount()
    data.flod_times = self:getRemainFoldCount()
    data.op_time = bee.getServerTime()
    data.card_player_ids = {}
    for _,v in pairs(self.ownedJokerList) do
        table.insert(data.card_player_ids, v.skillId)
    end
    data.formulas = {}
    data.ids = {}
    data.get_score = 0

    table.insert(self.operationDataList, data)
    print(json.encode(data))
end

function P:saveOperation(scoreList, jokerEffList)
    local data = self.operationDataList[#self.operationDataList]
    data.formulas = scoreList
    data.ids = jokerEffList
    data.get_score = math.floor(self.curChip * self.curPower * 100)
end

function P:gameOver()
    Net:sendReq("pb.GameOverREQ", {operations = self.operationDataList}, function (msg)
        self:gameOverCallback(msg)
    end)
end
function P:gameOverCallback(msg)
    if msg.code ~= 0 then
        UiManager:showTip({
            text = _T("TAB_JOKER_DEC_28"),
            button = 1,
            noClose = true,
            onSure = function()
                self:returnMainView()
            end
        })
        return
    end
    -- UiManager:showUI("BackpackClaimResult", {items = msg.rewards})
    
    BalSkillUtil:clearMarkSkill()
    BalSkillUtil:dispose()

    self.endlessTime = msg.endless_times or 0
    UiManager:showUI("HalloweenResult", {isWin = msg.is_pass, score = self.matchingScore, rewards = msg.rewards, hisScore = msg.his_score})
end

function P:returnMainView()
    GameModel:setSkipLobbyAutoPop(true)
    self.playing = false
    UiManager:showUI("LoadingLayer", {cb = function()
        bee.enterScene("MainScene", {afterShow = function()
            UiManager:showUI("HalloweenMain")
            UiManager:showUI("HalloweenJokerMain")
        end})
    end})
end

function P:inGame()
    return self.playing
end

--#endregion


--装饰方案
function P:setScheme(schemeId)
    self.scheme = DecorationModel:getInGameSchemeInfoById(schemeId)
end

function P:getScheme()
	if self.scheme then
		return self.scheme
	end
	return DecorationModel:getDefaultInGameCurScheme()
end

return P