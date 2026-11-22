local P = {
    ratio = 10000, --放大倍率

    --所有卡牌效果叠加倍率
    curAllCardEffectRate = 1,

    --售价折扣
    discount = 0,

    displayList = {}, --表现列表
    displaying = false,
    changeList = {}, --变动列表
    changing =  false,
    --表现等待tag
    displayTag = nil,

    scoreList = {}, --得分列表
    jokerEffList = {}, --鬼牌起效列表

    --特殊鬼牌id
    --重复触发
    JokerTriggerAgain = 94,
    --重复触发两次
    JokerTriggerTwice = 73,
    --重新触发所有得分牌
    JokerAllTriggerAgain = 64,

    
}
BalSkillUtil = P


--回合开始
function P:roundStart(jokers)
    --触发鬼牌效果 鬼牌计分
    self:triggerJokerOnTiming(jokers, Bal.EffectTriggerType.RoundStart)
    self:skillStartDisplay(Bal.DisplayType.RoundStart)
end

--获得鬼牌
function P:getJoker(joker)
    local config = tpl_fate_character[joker.skillId]
    local initAction = self["effectTypeInit" .. config.effect_type]
    if initAction then
        initAction(self, joker, config.effect_values)
    end

    --鬼牌效果变动 鬼牌数量变动
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.JokerCountChange)

    self:skillStartDisplay(Bal.DisplayType.GetJoker)
end
function P:initJokerEffect(joker)
    local config = tpl_fate_character[joker.skillId]
    local initAction = self["effectTypeInit" .. config.effect_type]
    if initAction then
        initAction(self, joker, config.effect_values, joker.skillParams.accCount)
    end
end
--售出鬼牌
function P:sellJoker(joker)
    local config = tpl_fate_character[joker.skillId]
    local removeAction = self["effectTypeRemove" .. config.effect_type]
    if removeAction then
        removeAction(self, joker, config.effect_values)
    end

    --触发鬼牌效果 出售鬼牌
    self:triggerJokerOnTiming(BalBattleModel.ownedJokerList, Bal.EffectTriggerType.SellCard)

    --鬼牌效果变动 鬼牌数量变动
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.JokerCountChange)
    --鬼牌效果变动 出售鬼牌
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.SellCard)

    self:skillStartDisplay(Bal.DisplayType.RemoveJoker)
end

--新增扑克
function P:AddNewPoker(pokerData)
    --鬼牌效果变动 牌组变动
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.GroupChange)
    --鬼牌效果变动 卡组剩余数量变动
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.GroupRemainChange)
    --鬼牌效果变动 强化卡牌变动
    if pokerData.enhance ~= nil and pokerData.enhance ~= 0 then
        self:checkJokerEffectChange(Bal.JokerEffectChangePoint.StrengthenPokerChange)
    end

    self:skillStartDisplay(Bal.DisplayType.GetPoker)
end

--删除扑克
function P:DestroyPoker(pokerData)
    --鬼牌效果变动 牌组变动
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.GroupChange)
    --鬼牌效果变动 摧毁卡牌
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.DestroyCard)
    --鬼牌效果变动 卡组剩余数量变动
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.GroupRemainChange)
    --鬼牌效果变动 强化卡牌变动
    if pokerData.enhance ~= nil and pokerData.enhance ~= 0 then
        self:checkJokerEffectChange(Bal.JokerEffectChangePoint.StrengthenPokerChange)
    end

    self:skillStartDisplay(Bal.DisplayType.RemovePoker)
end

--扑克出牌阶段
function P:showCardStage(pokers, jokers)
    --鬼牌效果变动 出牌
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.PlayCard)
    --鬼牌效果变动 出牌弃牌
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.PlayAndFoldCard)

    --触发鬼牌效果 确认出牌
    self:triggerJokerOnTiming(jokers, Bal.EffectTriggerType.ConfirmCard)

    --触发鬼牌效果 得分
    for _,v in pairs(pokers) do
        local pokerAction = function()
            local weaken = v.weaken
            --虚弱
            if weaken then
                table.insert(self.displayList, {poker = v, weaken = true})
            end

            if not weaken then
                --计分
                table.insert(self.displayList, {poker = v})
                --增强
                table.insert(self.displayList, {poker = v, enhance = v.enhance})
                --蜡封
                table.insert(self.displayList, {poker = v, seal = v.seal})
                --触发鬼牌效果
                self:triggerJokerOnTiming(jokers, Bal.EffectTriggerType.PokerScoring, v)
            end
            --红色蜡封
            if v.seal == Bal.SealType.Red and not weaken then
                table.insert(self.displayList, {poker = v, redSeal = true})
                table.insert(self.displayList, {poker = v, enhance = v.enhance})
                table.insert(self.displayList, {poker = v, seal = v.seal})
                self:triggerJokerOnTiming(jokers, Bal.EffectTriggerType.PokerScoring)
            end
        end
        
        --默认执行
        pokerAction()
        --重新触发
        local count = #jokers
        for i = 1, count do
            if jokers[i].skillId == self.JokerTriggerAgain then
                local cfg = tpl_fate_character[jokers[i].skillId]
                local check = self:effectType94(jokers[i], cfg.effect_values, v.data)
                if check then
                    pokerAction()
                end
            end
        end
    end

    --触发鬼牌效果 手牌计分
    self:triggerJokerOnTiming(jokers, Bal.EffectTriggerType.HandCardScoring)

    --触发鬼牌效果 鬼牌计分
    self:triggerJokerOnTiming(jokers, Bal.EffectTriggerType.JokerScoring)

    self.scoreList = {}
    self.jokerEffList = {}

    self:skillStartDisplay(Bal.DisplayType.Scoring)
end

--扑克弃牌阶段
function P:foldPoker(pokerData)
    --蜡封判定
    table.insert(self.displayList, {poker = pokerData, seal = pokerData.seal})
    --鬼牌效果变动 弃牌
    self:checkJokerEffectChange(Bal.JokerEffectChangePoint.FoldCard, {poker = pokerData})

    self:skillStartDisplay(Bal.DisplayType.FoldPoker)
end


--根据触发时机触发鬼牌
function P:triggerJokerOnTiming(jokers, triggerType, poker)
    for _,v in pairs(jokers) do
        local cfg = tpl_fate_character[v.skillId]
        if cfg.trigger == triggerType then
            table.insert(self.displayList, {joker = v, timing = "trigger", triggerPoker = poker})
        end
    end
end

--获得牌型的得分参数
function P:getCardTypeParams(type)
    return 2, 3
end

--卡牌效果表现
function P:skillStartDisplay(effType)
    if table.nums(self.displayList) <= 0 then
        local cacheScore = BalBattleModel.matchingScore
        if effType == Bal.DisplayType.Scoring then
            BalBattleModel.matchingScore = BalBattleModel.matchingScore + BalBattleModel.curChip * BalBattleModel.curPower
            BalBattleModel:saveOperation(self.scoreList, self.jokerEffList)
        end
        bee.emit("evt_BalTriggerEventOver", {effType = effType, score = cacheScore})
        return
    end
    local event = self.displayList[1]
    table.remove(self.displayList, 1)
    local waitTime = 0
    if event.poker then
        waitTime = self:pokerDisplay(event.poker, event.weaken, event.redSeal, event.enhance, event.seal) or 0
    end
    if event.joker then
        waitTime = self:jokerDisplay(event.joker, event.timing, event.triggerPoker) or 0
    end

    self.displayTag = bee.once(waitTime, function() self:skillStartDisplay(effType) end)
end

--扑克效果表现
function P:pokerDisplay(poker, weaken, redSeal, enhance, seal)
    --持续时间
    local waitTime = Bal.CardEffectKeepTime

    --削弱
    if weaken then
        --削弱提示
        bee.emit("evt_BalDisplayCardEffect", {poker = poker, effect = {weaken = true}})
        return waitTime
    end

    --红色蜡封
    if redSeal then
        --再来一次提示
        bee.emit("evt_BalDisplayCardEffect", {poker = poker, effect = {redSeal = true}})
        waitTime = waitTime + Bal.CardEffectKeepTime
    end

    --增强
    if enhance and enhance ~= 0 then
        local enhanceData = self:checkTriggerPokerEx(Bal.EffectTriggerType.PokerScoring, poker)
        if enhanceData ~= nil and enhanceData.trigger then
            self:triggerEffect(poker, enhanceData)
            -- bee.emit("evt_BalDisplayCardEffect", {poker = poker, effect = enhanceData})
            -- self:statEffect(enhanceData)
        end
        return waitTime
    end

    --蜡封
    if seal and seal ~= 0 then
        local sealData = self:checkTriggerPokerEx(Bal.EffectTriggerType.PokerScoring, poker)
        if sealData ~= nil and sealData.trigger then
            self:triggerEffect(poker, sealData)
            -- bee.emit("evt_BalDisplayCardEffect", {poker = poker, effect = sealData})
            -- self:statEffect(sealData)
        end
        return waitTime
    end

    --正常执行
    if enhance == nil and seal == nil then
        local effect = {rewardId = 1, rewardCount = (poker.value + poker.params.extraChips)}
        self:triggerEffect(poker, effect)
        -- bee.emit("evt_BalDisplayCardEffect", {poker = poker, effect = effect})
        -- self:statEffect(effect)
        return waitTime
    end
end

--鬼牌效果表现
function P:jokerDisplay(joker, timing, poker)
    --触发判定
    local triggerData = nil
    if timing == "trigger" then
        triggerData = self:checkJokerTrigger(joker, poker)
    elseif timing == "change" then
        triggerData = self:checkJokerChange(joker)
    end
    if triggerData == nil or not triggerData.trigger then
        return 0
    end

    --持续时间
    local waitTime = Bal.CardEffectKeepTime

    --执行
    self:triggerEffect(joker, triggerData, joker.skillId)
    -- bee.emit("evt_BalDisplayCardEffect", {joker = joker, effect = triggerData})
    -- self:statEffect(triggerData, joker.skillId)

    return waitTime
end

--鬼牌触发条件判断
function P:checkJokerTrigger(joker, poker)
    local targetData = {trigger = false}

    --失效
    if joker.invalid then
        return targetData
    end

    local cfg = tpl_fate_character[joker.skillId]
    --技能类型判断
    local data, data2 = self["effectType" .. cfg.effect_type](self, joker, cfg.effect_values, poker)
    if data then
        targetData.trigger = data.trigger
        if targetData.trigger == nil then
            targetData.trigger = true
        end
        targetData.rewardId = data.rewardId
        targetData.rewardCount = data.rewardCount
    end
    if data2 then
        targetData.rewardId2 = data.rewardId2
        targetData.rewardCount2 = data.rewardCount2
    end

    return targetData
end

--鬼牌效果变动
function P:checkJokerEffectChange(type, params)
    for _,v in pairs(BalBattleModel.ownedJokerList) do
        local config = tpl_fate_character[v.skillId]
        if config.mark == type then
            table.insert(self.displayList, {joker = v, timing = "change"})
        end
    end
end

--鬼牌效果变动判断
function P:checkJokerChange(joker)
    local cfg = tpl_fate_character[joker.skillId]
    local action = self["effectTypeChange" .. cfg.effect_type]
    if action then
        action(self, joker, cfg.effect_values)
        -- return {trigger = true}
    end
end

--执行效果
function P:triggerEffect(cardData, effect, jokerSkillId)
    if effect.rewardId == Bal.ParameterType.Chip then
        BalBattleModel.curChip = BalBattleModel.curChip + effect.rewardCount
    elseif effect.rewardId == Bal.ParameterType.Power then
        BalBattleModel.curPower = BalBattleModel.curPower + effect.rewardCount
    elseif effect.rewardId == Bal.ParameterType.MulPower then
        BalBattleModel.curPower = BalBattleModel.curPower * effect.rewardCount / BalSkillUtil.ratio
    end

    if jokerSkillId == nil then
        bee.emit("evt_BalDisplayCardEffect", {poker = cardData, effect = effect})
        self:statEffect(effect)
    else
        bee.emit("evt_BalDisplayCardEffect", {joker = cardData, effect = effect})
        self:statEffect(effect, jokerSkillId)
    end
end

--效果统计
function P:statEffect(effect, jokerSkillId)
    local data = {}
    if effect.rewardId == Bal.ParameterType.Chip then
        data.type = 1
        data.c_type = 1
    elseif effect.rewardId == Bal.ParameterType.Power then
        data.type = 2
        data.c_type = 1
    elseif effect.rewardId == Bal.ParameterType.MulPower then
        data.type = 2
        data.c_type = 2
    end

    if next(data) ~= nil then
        data.value = effect.rewardCount
        table.insert(self.scoreList, data)
        if jokerSkillId then
            table.insert(self.jokerEffList, jokerSkillId)
        end
    end
end

--#region 鬼牌效果

--直接触发奖励
function P:effectType1(jokerData, effVals)
    return {rewardId = effVals[1], rewardCount = effVals[2] - (jokerData.skillParams.accCount * (effVals[5] or 1))}
end
function P:effectTypeInit1(jokerData, effVals, count)
    BalBattleModel:changeParameterCount(effVals[1], effVals[2])
end
function P:effectTypeChange1(jokerData, effVals)
    if #effVals > 2 then
        local trigger = self:triggerProbability(effVals[3], effVals[4])
        if trigger then
            jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
            BalBattleModel:changeParameterCount(effVals[1], -effVals[5])
            if jokerData.skillParams.accCount * effVals[5] >= effVals[2] then
                return {deljoker = true}
            end
        end
    end
    return nil
end
function P:effectTypeRemove1(jokerData, effVals)
    if #effVals > 2 then
        local remainVal = effVals[2] - jokerData.skillParams.accCount * effVals[5]
        if remainVal > 0 then
            BalBattleModel:changeParameterCount(effVals[1], -remainVal)
        end
    end
end

--扑克牌得分时触发奖励
function P:effectType2(jokerData, effVals, poker)
    --弱化
    if poker.weaken then
        return
    end
    --条件
    local check = false
    if effVals[1] == 5 then
        check = jokerData.skillParams.randomSuit == poker.suit
    else
        check = effVals[1] == poker.suit
    end
    if not check then
        return
    end
    --概率
    local trigger = self:triggerProbability(effVals[2], effVals[3])
    if not trigger then
        return
    end

    return {trigger = true, rewardId = effVals[4], rewardCount = effVals[5]}
end
function P:effectTypeInit2(jokerData, effVals)
    if effVals[1] == 5 then
        local suit = self:getRandomSuit(jokerData.skillParams.randomSuit)
        jokerData.skillParams.randomSuit = suit
    end
end
function P:effectTypeChange2(jokerData, effVals)
    self:effectTypeInit2(jokerData, effVals)
end

--打出牌包含指定类型触发奖励
function P:effectType3(jokerData, effVals)
    local inculdeList = Bal.CardTypeIncludeDic[BalBattleModel.curCardType]
    --常规包含
    if table.keyof(inculdeList, effVals[1]) ~= nil then
        return {rewardId = effVals[2], rewardCount = effVals[3]}
    end
    --同花 判定小于同花的牌型
    if BalBattleModel.curCardType == Bal.CardType.Flush then
        local samePointDic = {}
        local pointList = {}
        for _,v in pairs(BalBattleModel.selectingCardDic) do
            if samePointDic[v.point] == nil then
                samePointDic[v.point] = 0
            end
            samePointDic[v.point] = samePointDic[v.point] + 1
            table.insert(pointList, v.point)
        end
        table.sort(pointList, function(a, b) return a < b end)

        local check = false
        if effVals[1] == Bal.CardType.Pair then
            for _,v in pairs(samePointDic) do
                if v >= 2 then
                    check = true
                    break
                end
            end
        elseif effVals[1] == Bal.CardType.ThreeKind then
            for _,v in pairs(samePointDic) do
                if v >= 3 then
                    check = true
                    break
                end
            end
        elseif effVals[1] == Bal.CardType.TwoPair then
            local pairCount = 0
            for _,v in pairs(samePointDic) do
                if v >= 2 then
                    pairCount = pairCount + 1
                    if pairCount == 2 then
                        check = true
                    end
                end
            end
        elseif effVals[1] == Bal.CardType.Straight then
            for i = 2, 5 do
                if pointList[i] == pointList[1] + (i - 1) and i == 5 then
                    check = true
                end
            end
            for i = 1, 5 do
                local cachePot = Bal.RoyalFlushValue[i]
                if table.keyof(pointList, cachePot) == nil then
                    break
                else
                    if i == 5 then
                        check = true
                    end
                end
            end
        end
        if check then
            return {rewardId = effVals[2], rewardCount = effVals[3]}
        end
    end

    --大于同花 判断同花牌型
    if BalBattleModel.curCardType > Bal.CardType.Flush and effVals[1] == Bal.CardType.Flush then
        local sameSuitDic = {}
        for _,v in pairs(Bal.PokerSuit) do
            sameSuitDic[v] = 0
        end
        for _,v in pairs(BalBattleModel.selectingCardDic) do
            if v.enhance == Bal.EnhanceType.Stone then --石头牌

            elseif v.enhance == Bal.EnhanceType.Wild then --万能牌
                for _,sv in pairs(Bal.PokerSuit) do
                    sameSuitDic[sv] = sameSuitDic[sv] + 1
                end
            else --普通牌
                sameSuitDic[v.suit] = sameSuitDic[v.suit] + 1
            end
        end
        for _,v in pairs(sameSuitDic) do
             if v == BalatroRule.limitPlayCardNum then
                return {rewardId = effVals[2], rewardCount = effVals[3]}
             end
        end
    end

    return {trigger = false}
end

--出牌数量触发奖励
function P:effectType4(jokerData, effVals)
    local cardCount = table.nums(BalBattleModel.selectingCardDic)
    local trigger = self:checkEquation(effVals[1], effVals[2], cardCount)
    if trigger then
        return {rewardId = effVals[3], rewardCount = effVals[4]}
    end
end

--空卡槽触发倍率
function P:effectType5(jokerData, effVals)
    local included = false
    for _,v in pairs(BalBattleModel.ownedJokerList) do
        if v.uid == jokerData.uid then
            included = true
        end
    end
    local emptyNum = BalBattleModel.maxJokerSlot - table.nums(BalBattleModel.ownedJokerList) - (not included and 1 or 0)
    emptyNum = math.max(0, emptyNum)
    return {rewardId = Bal.ParameterType.MulPower, rewardCount = effVals[1] + emptyNum * effVals[2]}
end
function P:effectTypeInit5(jokerData, effVals)
    local data = self:effectType5(jokerData, effVals)
    jokerData.skillParams.floatMulPower = data.rewardCount
end
function P:effectTypeChange5(jokerData, effVals)
    self:effectTypeInit5(jokerData, effVals)
end

--选择盲注后获得奖励
function P:effectType12(jokerData, effVals)
    local trigger = self:CheckBlindMeet(effVals[1])
    if trigger then
        return {rewardId = effVals[2], rewardCount = effVals[3], subType = effVals[4]}
    end
end

--指定卡牌得分触发奖励
function P:effectType14(jokerData, effVals, poker)
    --弱化
    if poker.weaken then
        return {trigger = false}
    end
    --条件
    local pokerTrigger = self:checkPokerMeet(effVals[1], effVals[2], poker)
    --概率
    local trigger = self:triggerProbability(effVals[3], effVals[4])
    if pokerTrigger and trigger then
        local targetData1 = {rewardId = effVals[5], rewardCount = effVals[6]}
        local targetData2 = nil
        if effVals[7] ~= nil then
            targetData2 = {rewardId = effVals[7], rewardCount = effVals[8]}
        end
        return targetData1, targetData2
    end
end

--完整牌组拥有指定卡牌触发奖励
function P:effectType19(jokerData, effVals)
    local num = 0
    if effVals[1] == 1 then --完整卡组中拥有指定点数
        for _,v in pairs(BalBattleModel.matchingPokerDataDic) do
            if v.point == effVals[2] then
                num = num + 1
            end
        end
    elseif effVals[1] == 2 then --完整卡组中拥有强化卡牌
        for _,v in pairs(BalBattleModel.matchingPokerDataDic) do
            if v.enhance == effVals[2] then
                num = num + 1
            end
        end
    end
    if num == 0 then
        return
    end
    return {rewardId = effVals[3], rewardCount = effVals[4] + (effVals[5] * num)}
end

--打出的牌包含指定牌型自身触发累积奖励
function P:effectType29(jokerData, effVals)
    if effVals[2] == Bal.ParameterType.Chip and jokerData.skillParams.floatChip > 0 then
        return {rewardId = effVals[2], rewardCount = jokerData.skillParams.floatChip}
    elseif effVals[2] == Bal.ParameterType.Power and jokerData.skillParams.floatPower > 0 then
        return {rewardId = effVals[2], rewardCount = jokerData.skillParams.floatPower}
    end
end
function P:effectTypeInit29(jokerData, effVals, count)
    if count and count >= 0 then
        if effVals[2] == Bal.ParameterType.Chip then
            jokerData.skillParams.floatChip = effVals[3] * count
        elseif effVals[2] == Bal.ParameterType.Power then
            jokerData.skillParams.floatPower = effVals[3] * count
        end
    end
end
function P:effectTypeChange29(jokerData, effVals)
    local samePointDic = {}
    local pointList = {}
    for _,v in pairs(BalBattleModel.selectingCardDic) do
        if samePointDic[v.point] == nil then
            samePointDic[v.point] = 0
        end
        samePointDic[v.point] = samePointDic[v.point] + 1
        table.insert(pointList, v.point)
    end
    table.sort(pointList, function(a, b) return a < b end)

    local check = false
    if effVals[1] == Bal.CardType.TwoPair then
        local pairCount = 0
        for _,v in pairs(samePointDic) do
            if v >= 2 then
                pairCount = pairCount + 1
                if pairCount == 2 then
                    check = true
                end
            end
        end
    elseif effVals[1] == Bal.CardType.Straight then
        for i = 2, 5 do
            if pointList[i] == pointList[1] + (i - 1) and i == 5 then
                check = true
            end
        end
        for i = 1, 5 do
            local cachePot = Bal.RoyalFlushValue[i]
            if table.keyof(pointList, cachePot) == nil then
                break
            else
                if i == 5 then
                    check = true
                end
            end
        end
    end

    if check then
        jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
        if effVals[2] == Bal.ParameterType.Chip then
            jokerData.skillParams.floatChip = jokerData.skillParams.floatChip + effVals[3]
        elseif effVals[2] == Bal.ParameterType.Power then
            jokerData.skillParams.floatPower = jokerData.skillParams.floatPower + effVals[3]
        end
    end
end

--直接触发奖励 出牌后削弱
function P:effectType30(jokerData, effVals)
    return {rewardId = effVals[1], rewardCount = effVals[2] - (effVals[3] * jokerData.skillParams.accCount)}
end
function P:effectTypeChange30(jokerData, effVals)
    jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
    if effVals[3] * jokerData.skillParams.accCount >= effVals[2] then
        return {deljoker = true}
    end
end

--牌组剩余数量兑换奖励
function P:effectType33(jokerData, effVals)
    local val = table.nums(BalBattleModel.matchingRemainIdList) * effVals[2]
    return {rewardId = effVals[1], rewardCount = val}
end

--打出指定牌型获得奖励
function P:effectType40(jokerData, effVals)
    if BalBattleModel.curCardType == jokerData.skillParams.randomCardType then
        return {rewardId = effVals[2], rewardCount = effVals[3]}
    end
end
function P:effectTypeInit40(jokerData, effVals)
    self:getRandomCardType(jokerData.skillParams.randomCardType)
end
function P:effectTypeChange40(jokerData, effVals)
    self:effectTypeInit40(jokerData, effVals)
end

--打出重复牌型获得奖励
function P:effectType41(jokerData, effVals)
    if BalBattleModel.playedCardTypeInRoundData[BalBattleModel.curCardType] > 1 then
        return {rewardId = effVals[1], rewardCount = effVals[2]}
    end
end

--手牌上限、出牌、弃牌次数变更
function P:effectType58(jokerData, effVals)
    local effCount = table.nums(effVals)
    for i = 1, effCount, 2 do
        local rType = effVals[i]
        if rType == Bal.ParameterType.Chip or rType == Bal.ParameterType.Power or rType == Bal.ParameterType.MulPower then
            return {rewardId = rType, rewardCount = effVals[i + 1]}
        end
    end
end
function P:effectTypeInit58(jokerData, effVals)
    local effCount = table.nums(effVals)
    for i = 1, effCount, 2 do
        BalBattleModel:changeParameterCount(effVals[i], effVals[i + 1])
    end
end
function P:effectTypeRemove58(jokerData, effVals)
    local effCount = table.nums(effVals)
    for i = 1, effCount, 2 do
        BalBattleModel:changeParameterCount(effVals[i], -effVals[i + 1])
    end
end

--商店手动刷新自身触发累积奖励
function P:effectType62(jokerData, effVals)
    if jokerData.skillParams.accCount == 0 then
        return
    end
    return {rewardId = effVals[1], rewardCount = effVals[2] * jokerData.skillParams.accCount}
end
function P:effectTypeChange62(jokerData, effVals)
    jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
end

--弃牌自身触发累积奖励
function P:effectType63(jokerData, effVals)
    return {rewardId = effVals[1], rewardCount = effVals[2] + effVals[3] * jokerData.skillParams.accCount}
end
function P:effectTypeChange63(jokerData, effVals)
    jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
    if effVals[2] + effVals[3] * jokerData.skillParams.accCount <= 0 then
        return {deljoker = true}
    end
end

--弃掉指定花色自身触发累积奖励
function P:effectType65(jokerData, effVals)
    if jokerData.skillParams.accCount == 0 then
        return
    end
    return {rewardId = effVals[2], rewardCount = effVals[3] * jokerData.skillParams.accCount}
end
function P:effectTypeInit65(jokerData, effVals, count)
    if effVals[1] == 5 then
        local suit = self:getRandomSuit(jokerData.skillParams.randomSuit)
        jokerData.skillParams.randomSuit = suit
    else
        jokerData.skillParams.randomSuit = effVals[1]
    end
end
function P:effectTypeChange65(jokerData, effVals, changeData)
    if changeData.type == Bal.JokerEffectChangePoint.FoldCard then
        if changeData.foldPoker.data.suit == jokerData.skillParams.randomSuit then
            jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
        end
    elseif changeData.type == Bal.JokerEffectChangePoint.RoundOver then
        self:effectTypeInit65(jokerData, effVals)
    end
end

--弃掉指定扑克牌自身触发累积奖励
function P:effectType83(jokerData, effVals)
    return {rewardId = effVals[2], rewardCount = effVals[3] + effVals[4] * jokerData.skillParams.accCount}
end
function P:effectTypeChange83(jokerData, effVals, changeData)
    if changeData.foldPoker.data.point ~= effVals[1] then
        return
    end
    jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
end

--弃掉一定数量的扑克牌自身触发累积奖励
function P:effectType90(jokerData, effVals)
    local count = math.floor(jokerData.skillParams.accCount / effVals[1])
    return {rewardId = effVals[2], rewardCount = effVals[3] + effVals[4] * count}
end
function P:effectTypeChange90(jokerData, effVals)
    jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
end

--根据出牌数量自身触发累积奖励
function P:effectType93(jokerData, effVals)
    local val = effVals[4] + jokerData.skillParams.accCount * effVals[5]
    if val == 0 then
        return
    end
    return {rewardId = effVals[3], rewardCount = val}
end
function P:effectTypeChange93(jokerData, effVals)
    local trigger = self:CheckEquation(effVals[1], effVals[2], table.nums(BalBattleModel.playedPokerList))
    if trigger then
        jokerData.skillParams.accCount = jokerData.skillParams.accCount + 1
    end
end

--重新触发指定扑克牌
function P:effectType94(jokerData, effVals, poker)
    --弱化
    if poker.weaken then
        return
    end
    --条件
    local check = false
    if effVals[1] == 3 then
        if table.keyof(Bal.SmallNumberType, poker.point) ~= nil then
            check = true
        end
    elseif effVals[1] == 9 then
        if table.keyof(Bal.PokerHumanType, poker.point) ~= nil then
            check = true
        end
    end
    --触发
    return check
end

--指定扑克本次出牌首次得分获得奖励
function P:effectType96(jokerData, effVals, poker)
    local check = false
    local firPokerUid = 0
    local cardCount = table.nums(BalBattleModel.curScoringList)
    for i = 1, cardCount do
        if check then
            break
        end
        firPokerUid = BalBattleModel.curScoringList[i]
        local firPokerData = BalBattleModel.matchingPokerDataDic[firPokerUid]
        check = self:checkPokerMeet(effVals[1], effVals[2], firPokerData)
    end
    if check and poker.uid == firPokerUid then
        return {rewardId = effVals[3], rewardCount = effVals[4]}
    end
end


--移除卡牌计数
function P:clearMarkSkill()
    for _,v in pairs(BalBattleModel.ownedJokerList) do
        local skillCfg = tpl_fate_character[v.skillId]
        if skillCfg.mark then
            v.skillParams.accCount = 0
            self:initJokerEffect(v)
        end
    end
end

--#endregion


--扑克强化触发条件判定 增强、蜡封
function P:checkTriggerPokerEx(triggerType, pokerData)
    local targetData = {trigger = false}
    local config = tpl_[pokerData.seal]
    if config == nil then return end

    if config.trigger ~= triggerType then
        return nil
    end

    local data, data2 = self["strengthenType" .. config.effect_type](self, pokerData, config.effect_values)
    if data then
        targetData.trigger = data.trigger or true
        targetData.rewardId = data.rewardId
        targetData.rewardCount = data.rewardCount
    end
    if data2 then
        targetData.rewardId2 = data.rewardId2
        targetData.rewardCount2 = data.rewardCount2
    end
    return targetData
end

--计分时直接获得奖励
function P:strengthenType1(pokerData, effVals)
    return {rewardId = effVals[1], rewardCount = effVals[2]}
end
function P:strengthenTypeChange1(pokerData, effVals)
    local trigger = self:triggerProbability(effVals[3], effVals[4])
    if trigger then
        return {delpoker = true}
    end
end

--计分时还在手牌内获得奖励
function P:strengthenType3(pokerData, effVals)
    if table.keyof(BalBattleModel.displayPokerList, pokerData.uid) == nil then
        return
    end
    return {rewardId = effVals[1], rewardCount = effVals[2]}
end

--计分时直接获得奖励
function P:strengthenType4(pokerData, effVals)
    return {rewardId = effVals[1], rewardCount = effVals[2]}
end

--回合结束后还在手牌获得奖励
function P:strengthenType5(pokerData, effVals)
    if table.keyof(BalBattleModel.displayPokerList, pokerData.uid) == nil then
        return
    end
    return {rewardId = effVals[1], rewardCount = effVals[2]}
end

--计分时概率获得奖励
function P:strengthenType6(pokerData, effVals)
    local trigger1 = self:triggerProbability(effVals[1], effVals[2])
    local data1 = nil
    if trigger1 then
        data1 = {rewardId = effVals[3], rewardCount = effVals[4]}
    end
    local trigger2 = self:triggerProbability(effVals[5], effVals[6])
    local data2 = nil
    if trigger2 then
        data2 = {rewardId = effVals[7], rewardCount = effVals[8]}
    end
    return data1, data2
end

--打出并计分时，生命恢复
function P:strengthenType8(pokerData, effVals)
    return {restore = effVals[1]}
end

--丢弃时，对手cd增加
function P:strengthenType9(pokerData, effVals)
    local trigger = self:triggerProbability(effVals[1], effVals[2])
    if trigger then
        return {bossCD = effVals[3]}
    end
end


--#region 独立功能

--触发概率 分子 分母
function P:triggerProbability(num, den)
    if num == den then return true end

    local ratio = (num * self.curAllCardEffectRate) / den * self.ratio
    local probability = BalBattleModel:GetRandom(0, self.ratio)
    return ratio >= probability
end

--获取随机花色
function P:getRandomSuit(weedout)
    local list = {}
    for _,v in pairs(Bal.PokerSuit) do
        if v ~= weedout then
            table.insert(list, v)
        end
    end
    local suitNum = table.nums(list)
    local random = BalBattleModel:GetRandom(0, suitNum) + 1
    return list[random]
end

--等式判定
function P:checkEquation(eType, argsVal, value)
    local trigger = false
    if eType == Bal.EquationType.Greater then
        if value > argsVal then trigger = true end
    elseif eType == Bal.EquationType.Less then
        if value < argsVal then trigger = true end
    elseif eType == Bal.EquationType.Equal then
        if value == argsVal then trigger = true end
    elseif eType == Bal.EquationType.GreaterOrEqual then
        if value >= argsVal then trigger = true end
    elseif eType == Bal.EquationType.LessOrEqual then
        if value <= argsVal then trigger = true end
    end
    return trigger
end

--盲注选择判定
function P:checkBlindMeet(argsType)
    if argsType == Bal.SelectBlindType.All then
        return true
    elseif argsType == Bal.SelectBlindType.BS then
        if BalBattleModel.anteRound == Bal.BlindType.Normal or BalBattleModel.anteRound == Bal.BlindType.Elite then
            return true
        end
    elseif argsType == Bal.SelectBlindType.Boss then
        if BalBattleModel.anteRound == Bal.BlindType.Boss then
            return true
        end
    end
    return false
end

--出牌扑克判定
function P:checkPokerMeet(argsType, argsVal, poker)
    local trigger = false
    if argsType == 1 then --单个点数
        trigger = argsVal == poker.point
    elseif argsType == 2 then --非人头牌牌
        local key = table.keyof(Bal.PokerUnHumanType, poker.point)
        trigger = key ~= nil
    elseif argsType == 3 then --人头牌
        local key = table.keyof(Bal.PokerHumanType, poker.point)
        trigger = key ~= nil
    elseif argsType == 4 then --斐波那契 1、2、3、5、8
        local key = table.keyof(Bal.FibonacciType, poker.point)
        trigger = key ~= nil
    elseif argsType == 5 then --偶数 2、4、6、8、10
        local key = table.keyof(Bal.EvenNumberType, poker.point)
        trigger = key ~= nil 
    elseif argsType == 6 then --奇数 A、3、5、7、9
        local key = table.keyof(Bal.OddNumberType, poker.point)
        trigger = key ~= nil
    elseif argsType == 7 then --Q、K
        trigger = (poker.point == 12 or poker.point == 13)
    elseif argsType == 8 then --4、10
        trigger = (poker.point == 4 or poker.point == 10)
    end
    return trigger
end

--获取随机牌型
function P:getRandomCardType(weedout)
    local list = {}
    for _,v in pairs(Bal.CardType) do
        if v ~= weedout then
            table.insert(list, v)
        end
    end
    local cardTypeNum = table.nums(list)
    local random = BalBattleModel:GetRandom(0, cardTypeNum) + 1
    return list[random]
end

--获取价格折扣
function P:getDiscount(cost)
    local tarCost = cost * (1 - (self.discount / self.ratio))
    return math.max(1, math.floor(tarCost))
end

--计数翻译
function P:getJokerDecMark(cfg, jokerData)
    local dec = ""
    if cfg.effect_type == 29 then
        dec = _F(cfg.dec, jokerData.skillParams.accCount * cfg.effect_values[3])
    end
    return dec
end

--#endregion


--清除数据
function P:dispose()
    self.displayList = {}
    scheduler:removeTag(self.displayTag)
    self.displayTag = nil
end

return P