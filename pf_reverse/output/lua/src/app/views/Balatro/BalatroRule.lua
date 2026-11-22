local P = {
    --出牌上限
    limitPlayCardNum = 5,
    --默认牌组
    defaultCardData = nil,
}
BalatroRule = P

--测试
function P:TestFunction(...)
    if self.defaultCardData == nil then
        PokerUtil:CreatePokerGroup()
    end

    local list = {}
    for _,v in pairs({...}) do
        local poker = self.defaultCardData[v]
        table.insert(list, poker)
    end
    local data = self:CheckCardType(list)
end

--牌型判定
function P:CheckCardType(list)
    if next(list) == nil then
        return nil
    end
    local suitDic, valueDic = self:AnalysisCardGroupData(list)
    return self:AnalysisCardGroupType(suitDic, valueDic)
end

--解析卡组数据
function P:AnalysisCardGroupData(list)
    --花色数据
    local suitDic = {}
    --数值数据
    local valueDic = {}

    for _,v in pairs(list) do
        self:AddSuitData(suitDic, v.suit, v.uid)

        if valueDic[v.point] == nil then
            valueDic[v.point] = {}
            valueDic[v.point].num = 0
            valueDic[v.point].idList = {}
        end
        valueDic[v.point].num = valueDic[v.point].num + 1
        table.insert(valueDic[v.point].idList, v.uid)
    end
    return suitDic, valueDic
end

--添加花色数据
function P:AddSuitData(suitDic, suitType, uid)
    if suitDic[suitType] == nil then
        suitDic[suitType] = {}
        suitDic[suitType].num = 0
        suitDic[suitType].idList = {}
    end
    suitDic[suitType].num = suitDic[suitType].num + 1
    table.insert(suitDic[suitType].idList, uid)
end

--解析牌型
function P:AnalysisCardGroupType(suitDic, valueDic)
    local targetData = {}
    local targetTypeList = {}

    --同花判定
    local flush = self:ChackFlush(suitDic, targetTypeList, targetData)

    --数值统计
    local cacheValueList = {} --数值列表
    local cacheValueNumList = {} --数值数量列表
    for k,v in pairs(valueDic) do
        table.insert(cacheValueList, k)
        table.insert(cacheValueNumList, v.num)
    end
    table.sort(cacheValueList, function(a, b) return a < b end)
    table.sort(cacheValueNumList, function(a, b) return a > b end)

    --顺子判定
    local fiveStraightType = self:ChackStraight(valueDic, cacheValueList, targetTypeList, targetData, flush)

    if cacheValueNumList[1] == Bal.PokerSameValueType.Five then
        self:SetFiveKind(valueDic, targetTypeList, targetData, flush)
    elseif cacheValueNumList[1] == Bal.PokerSameValueType.Four then
        self:SetFourKind(valueDic, targetTypeList, targetData)
    elseif cacheValueNumList[1] == Bal.PokerSameValueType.Three then
        if cacheValueNumList[2] == Bal.PokerSameValueType.Two then
            self:SetFullHouse(valueDic, targetTypeList, targetData, flush)
        else
            self:SetThreeKind(valueDic, targetTypeList, targetData)
        end
    elseif cacheValueNumList[1] == Bal.PokerSameValueType.Two then
        if cacheValueNumList[2] == Bal.PokerSameValueType.Two then
            self:SetTowPair(valueDic, targetTypeList, targetData)
        else
            self:SetPair(valueDic, targetTypeList, targetData)
        end
    else
        self:SetHighCard(valueDic, cacheValueList, targetTypeList, targetData)
    end

    table.sort(targetTypeList, function(a, b) return a > b end)

    local data = {}
    data.type = targetTypeList[1] or Bal.CardType.HighCard
    data.cardList = {}
    local typeList = targetData[data.type]
    if typeList ~= nil then
        for _,v in pairs(typeList) do
            table.insert(data.cardList, v)
        end
    end

    data.royalStraight = fiveStraightType == Bal.PokerStraightType.Royal and flush
    return data
end

--同花判定
function P:ChackFlush(suitDic, targetTypeList, targetData)
    for _,v in pairs(suitDic) do
        if v.num == self.limitPlayCardNum then
            table.insert(targetTypeList, Bal.CardType.Flush)
            targetData[Bal.CardType.Flush] = v.idList
            return true
        end
    end
    return false
end

--顺子判定
function P:ChackStraight(valueDic, cacheValueList, targetTypeList, targetData, flush)
    local listCount = table.nums(cacheValueList)
    local cacheIdList = {}

    local fiveStraightType = Bal.PokerStraightType.None
    local fiveIdList = {}
    if listCount == self.limitPlayCardNum then
        -- 正常顺序
        local strVal = cacheValueList[1]
        table.insert(cacheIdList, valueDic[strVal].idList[1])
        for i = 2, listCount do
            local checkVal = cacheValueList[i]
            if checkVal == strVal + (i - 1) then
                table.insert(cacheIdList, valueDic[checkVal].idList[1])
                if i == listCount then
                    fiveStraightType = Bal.PokerStraightType.Normal
                    fiveIdList = clone(cacheIdList)
                end
            else
                cacheIdList = {}
                break
            end
        end

        -- 10JQKA
        for i = 1, listCount do
            local checkVal = Bal.RoyalFlushValue[i]
            if table.keyof(cacheValueList, checkVal) ~= nil then
                table.insert(cacheIdList, valueDic[checkVal].idList[1])
                if i == listCount then
                    fiveStraightType = Bal.PokerStraightType.Royal
                    fiveIdList = clone(cacheIdList)
                end
            else
                cacheIdList = {}
                break
            end
        end
    end

    if fiveStraightType ~= Bal.PokerStraightType.None then
        if targetData[Bal.CardType.Straight] == nil then
            table.insert(targetTypeList, Bal.CardType.Straight)
        end
        targetData[Bal.CardType.Straight] = fiveIdList

        if flush then
            if targetData[Bal.CardType.StraightFlush] == nil then
                table.insert(targetTypeList, Bal.CardType.StraightFlush)
            end
            targetData[Bal.CardType.StraightFlush] = fiveIdList
            
            if fiveStraightType == Bal.PokerStraightType.Royal then
                table.insert(targetTypeList, Bal.CardType.RoyalFlush)
                targetData[Bal.CardType.RoyalFlush] = fiveIdList
            end
        end
    end
    return fiveStraightType
end

--五条数据 
function P:SetFiveKind(valueDic, targetTypeList, targetData, flush)
    table.insert(targetTypeList, Bal.CardType.FiveKind)
    for _,v in pairs(valueDic) do
        if v.num == Bal.PokerSameValueType.Five then
            targetData[Bal.CardType.FiveKind] = v.idList
            break
        end
    end
    if flush then
        table.insert(targetTypeList, Bal.CardType.FiveKindFlush)
        targetData[Bal.CardType.FiveKindFlush] = targetData[Bal.CardType.FiveKind]
    end
end

--四条数据
function P:SetFourKind(valueDic, targetTypeList, targetData)
    table.insert(targetTypeList, Bal.CardType.FourKind)
    for _,v in pairs(valueDic) do
        if v.num == Bal.PokerSameValueType.Four then
            targetData[Bal.CardType.FourKind] = v.idList
            break
        end
    end
end

--三条数据
function P:SetThreeKind(valueDic, targetTypeList, targetData)
    table.insert(targetTypeList, Bal.CardType.ThreeKind)
    for _,v in pairs(valueDic) do
        if v.num == Bal.PokerSameValueType.Three then
            targetData[Bal.CardType.ThreeKind] = v.idList
            break
        end
    end
end

--葫芦数据
function P:SetFullHouse(valueDic, targetTypeList, targetData, flush)
    table.insert(targetTypeList, Bal.CardType.FullHouse)
    targetData[Bal.CardType.FullHouse] = {}
    for _,v in pairs(valueDic) do
        if v.num == Bal.PokerSameValueType.Three then
            for _,iv in pairs(v.idList) do
                table.insert(targetData[Bal.CardType.FullHouse], iv)
            end
        elseif v.num == Bal.PokerSameValueType.Two then
            for _,iv in pairs(v.idList) do
                table.insert(targetData[Bal.CardType.FullHouse], iv)
            end
        end
    end
    if flush then
        table.insert(targetTypeList, Bal.CardType.FullHouseFlush)
        targetData[Bal.CardType.FullHouseFlush] = targetData[Bal.CardType.FullHouse]
    end
end

--两对数据
function P:SetTowPair(valueDic, targetTypeList, targetData)
    table.insert(targetTypeList, Bal.CardType.TwoPair)
    targetData[Bal.CardType.TwoPair] = {}
    for _,v in pairs(valueDic) do
        if v.num == Bal.PokerSameValueType.Two then
            for _,iv in pairs(v.idList) do
                table.insert(targetData[Bal.CardType.TwoPair], iv)
            end
        end
    end
end

--一对数据
function P:SetPair(valueDic, targetTypeList, targetData)
    table.insert(targetTypeList, Bal.CardType.Pair)
    targetData[Bal.CardType.Pair] = {}
    for _,v in pairs(valueDic) do
        if v.num == Bal.PokerSameValueType.Two then
            targetData[Bal.CardType.Pair] = v.idList
            break
        end
    end
end

--高牌数据
function P:SetHighCard(valueDic, valueList, targetTypeList, targetData)
    if table.nums(valueDic) == 0 then return end

    table.insert(targetTypeList, Bal.CardType.HighCard)
    local val = valueList[table.nums(valueList)]
    if valueList[1] == 1 then val = 1 end
    targetData[Bal.CardType.HighCard] = valueDic[val].idList
end


return P