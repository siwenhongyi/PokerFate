local P = class("IngameReplay", UiFullView)

------------------ 回放的玩法类型 ------------------
REPLAY_GAME_TYPE = {
    All = 0,
    Poker = 1,
    Omaha = 2,
    AllInPoker = 3,
    Friend = 4,
    SNG = 5,
    MTT = 6,
}

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local LeftTop = self:find("LeftTop", AnimRoot)
    local Tab = self:find("Left/TAB", AnimRoot)
    local Center = self:find("Center", AnimRoot)
    local Bottom = self:find("Bottom", AnimRoot)

    self.NearGameToggle = self:find("TabToggle/Tab01Toggle", Tab)
    bee.onCheck(self.NearGameToggle, function(isOn) self:setNearGameData(isOn) end)
    self.CollectToggle = self:find("TabToggle/Tab02Toggle", Tab)
    bee.onCheck(self.CollectToggle, function(isOn) self:setCollectData(isOn) end)
    self.ReplayList = self:find("IngameReplayList", Center)
    self.ReplayScroll = self.ReplayList:GetComponent("ScrollRect")
    self.ReplayScroll.onValueChanged:AddListener(function() self:onScrolling() end)
    self.ScrollBar = self:find("ScrollBar", Center)
    self.Item = self:find("Item", self.ReplayList)
    self.PageTip = self:find("Text", Bottom)
    self.NoDataTip = self:find("Empty", Center)

    local Refresh = self:find("Refresh", Center)
    self.RefreshButton = self:find("RefreshButton", Refresh)
    self.FilterButton = self:find("FilterButton", Refresh)
    self.FilterText = self:find("FilterButton/Text", Refresh)
    self.ArrowTran = self:find("FilterButton/common_panel_black_filter_button_arrow", Refresh).transform
    self.DropDown = self:find("DropDown", Refresh)
    self.DropDownRoot = self:find("DropDown/common_panel_black_filter_list", Refresh)
    self.DropDownItem = self:find("DropDown/DropDownItem", Refresh)
    self.MaskButton = self:find("Mask", Refresh)

    self.dropItems = {}

    bee.addClick(self:find("CloseButton", LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self.MaskButton, function() self:switchDropDownPart(false) end)
    bee.addClick(self.RefreshButton, function() self:reReqData() end)

    self.List = UiListEx:create(self.ReplayList)
    self.List:setWidth(230)
    self.List:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.List:setRefreshFunc(function(data, item)
        self:refreshItem(data, item)
    end)

    self.InitCollect = false
    self.InNear = false
    self.InCollect = false
    self.NearGameList = {}
    self.CollectList = {}
    self.NearSkip = 0
    self.CollectSkip = 0
    self.SaveNearType = REPLAY_GAME_TYPE.All
    self.SaveCollectType = REPLAY_GAME_TYPE.All
    self.NearTotal = 0
    self.CollectTotal = 0

    self.ReplayTypeDic = {
        [REPLAY_GAME_TYPE.Poker] = {GAME_GAME_TYPE.LOBBY_HOLDEM_GAME, GAME_GAME_TYPE.TRAINING_HOLDEM_GAME},
        [REPLAY_GAME_TYPE.Omaha] = {GAME_GAME_TYPE.LOBBY_OMAHA_GAME, GAME_GAME_TYPE.TRAINING_OMAHA_GAME},
        [REPLAY_GAME_TYPE.AllInPoker] = {GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN},
        [REPLAY_GAME_TYPE.Friend] = {GAME_GAME_TYPE.FRIEND_HOLDEM_GAME},
        [REPLAY_GAME_TYPE.SNG] = {GAME_GAME_TYPE.SNG_HOLDEM_GAME, GAME_GAME_TYPE.SNG_OMAHA_GAME, GAME_GAME_TYPE.SNG_TRAIN_GAME},
        [REPLAY_GAME_TYPE.MTT] = {GAME_GAME_TYPE.MTT_HOLDEM_GAME}}
    self.ReplayTypeLabDic = {
        [REPLAY_GAME_TYPE.All] = "LAB_FRIROOM_034",
        [REPLAY_GAME_TYPE.Poker] = "LAB_POKER_GAME",
        [REPLAY_GAME_TYPE.Omaha] = "LAB_OMAHA",
        [REPLAY_GAME_TYPE.AllInPoker] = "LAB_ALLIN_01",
        [REPLAY_GAME_TYPE.Friend] = "LAB_FRIROOM_001",
        [REPLAY_GAME_TYPE.SNG] = "LAB_TOURNAMENT_SNG",
        [REPLAY_GAME_TYPE.MTT] = "LAB_TOURNAMENT_MTT"}

end

function P:onShow()
    self.NoDataTip:SetActive(false)
    self.ScrollBar:SetActive(true)
    bee.setToggle(self.NearGameToggle, true)

    self:InitDropDown()

    -- bee.setText(self.PageTip, _F("LAB_SAVE_LIMIT", PlayerModel:getCurRecord() .. " / " .. PlayerModel:getRecordNum()))

    -- Net:post("/collCard/list", {t = 1, lang = LAN:getLanguage()}, function(data)
    --     if 0 == data.code then
    --         if data.list then
    --             self.ReplayDataList = data.list
    --             self.NoDataTip:SetActive(#data.list == 0)
    --             self.List:setDatas(data.list)
    --             PlayerModel:setCurRecord(#data.list)
    --             bee.setText(self.PageTip, _F("LAB_SAVE_LIMIT", #data.list .. " / " .. PlayerModel:getRecordNum()))
    --         else
    --             self.NoDataTip:SetActive(true)
    --         end
    --     end
    -- end)

    -- 任务进度-查看牌局回放
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.CardDeck)

    bee.logEvent("history-lobby")
end

function P:InitDropDown()
    local count = table.nums(REPLAY_GAME_TYPE)
    for i = 0, count - 1 do
        local item = {}
        local itemGo = CU.GameObject.Instantiate(self.DropDownItem, self.DropDownRoot.transform, false)
        itemGo:SetActive(true)
        item.type = i
        item.go = itemGo
        item.on = bee.find("On", itemGo)
        item.off = bee.find("Off", itemGo)
        local str = _T(self.ReplayTypeLabDic[i])
        bee.setText(bee.find("On/Text", itemGo), str)
        bee.setText(bee.find("Off/Text", itemGo), str)
        -- bee.find("Off", item):SetActive(false)
        bee.addClick(itemGo, function()
            self:filterType(i)
            self:switchDropDownPart(false)
        end)
        table.insert(self.dropItems, item)
    end

    bee.addClick(self.FilterButton, function()
        self:switchDropDownPart(true)
    end)

    local dropDownTran = self.DropDownRoot:GetComponent("RectTransform")
    dropDownTran.sizeDelta = bee.v2(dropDownTran.sizeDelta.x, (50 + 10) * count + 40)
end
function P:switchDropDownPart(sw)
    self.MaskButton:SetActive(sw)
    self.DropDown:SetActive(sw)
    self.ArrowTran.localEulerAngles = bee.v3(0, 0, sw and 0 or 180)

    if sw then
        local curType
        if self.InNear then
            curType = self.SaveNearType
        elseif self.InCollect then
            curType = self.SaveCollectType
        end
        for _,v in pairs(self.dropItems) do
            v.on:SetActive(v.type == curType)
            v.off:SetActive(v.type ~= curType)
        end
    end
end

function P:setNearGameData(isOn, type)
    Game:playSound("ui_tab_switch_1")
    self.InNear = isOn
    if not isOn then
        return
    end

    if self.NearSkip == 0 then
        Net:post("collCard/recentlyCardList", {skip = self.NearSkip, lang = LAN:getLanguage()}, function(data)
            if 0 == data.code then
                self.NearSkip = table.nums(data.list)
                if data.list then
                    self.NearGameList = data.list
                    self.NearTotal = data.total
                end
                self:filterType(type or REPLAY_GAME_TYPE.All)
            end
        end)
    else
        self:filterType(self.SaveNearType)
    end
    bee.setText(self.PageTip, _F("LAB_PLAYBACK3", PlayerModel:getRecentHistoryLimit()))

end

function P:setCollectData(isOn, type)
    Game:playSound("ui_tab_switch_1")
    self.InCollect = isOn
    if not isOn then
        return
    end

    if not self.InitCollect then
        self.InitCollect = true
        Net:post("collCard/list", {skip = 0, lang = LAN:getLanguage()}, function(data)
            if 0 == data.code then
                if data.list then
                    self.CollectList = data.list
                end
                self.CollectSkip = table.nums(data.list)
                self.CollectTotal = data.total
                PlayerModel:setCurRecord(self.CollectTotal)
                self:filterType(type or REPLAY_GAME_TYPE.All)
                bee.setText(self.PageTip, _F("LAB_SAVE_LIMIT", string.format("%s / %s", self.CollectTotal, PlayerModel:getRecordNum())))
            end
        end)
    else
        self:filterType(self.SaveCollectType)
        bee.setText(self.PageTip, _F("LAB_SAVE_LIMIT", string.format("%s / %s", PlayerModel:getCurRecord(), PlayerModel:getRecordNum())))
    end
end

--刷新数据
function P:reReqData()
    if self.InNear then
        self.NearSkip = 0
        self.NearGameList = {}
        self.List:moveToYItem(1, false)
        self:setNearGameData(true, self.SaveNearType)
    end
    if self.InCollect then
        self.CollectSkip = 0
        self.CollectGameList = {}
        self.List:moveToYItem(1, false)
        self:setCollectData(true, self.SaveCollectType)
    end
end

--刷新item
function P:refreshItem(data, item)
    local ImageCards = {
        self:find("ImageCard1", item),
        self:find("ImageCard2", item),
        self:find("ImageCard3", item),
        self:find("ImageCard4", item),
        self:find("ImageCard5", item),
    }
    local d = tpl_card_back[PlayerModel:getCurCardBack()]
    for i = 1, 5 do
        if data.cards[i] and data.cards[i] > 0 then
            bee.setIcon(ImageCards[i], GF.getCardImageByCode(data.cards[i]))
        else
            bee.setIcon(ImageCards[i], d.image)
        end
    end
    local title = GameModel:getReplayTitle(data)
    bee.setText(self:find("TextTitle", item), title)
    
    local TextAdd, TextDec = self:find("TextAdd", item), self:find("TextDec", item)
    local TextCardType
    if data.profit >= 0 then
        TextAdd:SetActive(true)
        TextDec:SetActive(false)
        if data.profit > 0 then
            bee.setText(TextAdd, "+" .. _N(data.profit))
        else
            bee.setText(TextAdd, _N(data.profit))
        end
        self:find("ingame_replay_lose", item):SetActive(false)
        self:find("ingame_replay_win", item):SetActive(true)
        self:find("ingame_replay_card_type_02", item):SetActive(true)
        self:find("ingame_replay_card_type_01", item):SetActive(false)
        TextCardType = self:find("ingame_replay_card_type_02/TextCardType", item)
    else
        TextAdd:SetActive(false)
        TextDec:SetActive(true)
        bee.setText(TextDec, "-" .. _N(-data.profit))
        self:find("ingame_replay_lose", item):SetActive(true)
        self:find("ingame_replay_win", item):SetActive(false)
        self:find("ingame_replay_card_type_02", item):SetActive(false)
        self:find("ingame_replay_card_type_01", item):SetActive(true)
        TextCardType = self:find("ingame_replay_card_type_01/TextCardType", item)
    end
    if data.hand_type > 0 or data.hand_type < 0 then
        bee.setText(TextCardType, _T(POKER_TYPE_NAME[data.hand_type]))
    else
        local _, cardType = PKHelper.getHoldemType({data.cards[1], data.cards[2]}, {data.cards[3], data.cards[4], data.cards[5], data.cards[6], data.cards[7]})
        bee.setText(TextCardType, _T(cardType))
    end

    local CollectButton = self:find("CollectButton", item)
    CollectButton:SetActive(self.InNear)
    if self.InNear then
        self:refreshCollectButton(CollectButton, data.collected)
        bee.removeAllClick(CollectButton)
        bee.addClick(CollectButton, function()
            if data.collected then
                Net:post("/collCard/update", {del_id = data.gameid, lang = LAN:getLanguage()}, function(d)
                    if 0 == d.code then
                        data.collected = not data.collected
                        self:refreshCollectButton(CollectButton, data.collected)
                        self.CollectSkip = self.CollectSkip - 1
                        self.CollectTotal = self.CollectTotal - 1
                        PlayerModel:setCurRecord(self.CollectTotal)
                        for k,v in pairs(self.CollectList) do
                            if v.gameid == data.gameid then
                                table.remove(self.CollectList, k)
                                break
                            end
                        end
                    end
                end)
            else
                if PlayerModel:getCurRecord() >= PlayerModel:getRecordNum() then
                    GameModel:getReplayList(function(d)
                        if 0 == d.code then
                            if d.list and #d.list > 0 then
                                UiManager:showTip({
                                    text = _F("LAB_DEL_PLAYBACK_TIP5", GameModel:getReplayTitle(d.data)),
                                    sureStr = _T("LAB_SAVE"),
                                    cancelStr = _T("LAB_DEL_PLAYBACK_TIP6"),
                                    onSure = function()
                                        self:changeReplay(d.data.gameid, data, CollectButton)
                                    end,
                                    onCancel = function()
                                    end,
                                })
                            end
                        end
                    end)
                else
                    self:saveData(data, CollectButton)
                end
            end
        end)
    end

    local DeleteButton = self:find("DeleteButton", item)
    DeleteButton:SetActive(self.InCollect)
    if self.InCollect then
        bee.removeAllClick(DeleteButton)
        bee.addClick(DeleteButton, function()
            UiManager:showTip({
                text = _T("LAB_DEL_PLAYBACK_TIP") .. "\n" .. title,
                onSure = function()
                    Net:post("/collCard/update", {
                        del_id = data.gameid,
                        lang = LAN:getLanguage(),
                    }, function(d)
                        if 0 == d.code then
                            self.List:removeData(data)
                            table.removebyvalue(self.CollectList, data)
                            self.CollectSkip = self.CollectSkip - 1
                            self.CollectTotal = #d.gameids
                            PlayerModel:setCurRecord(self.CollectTotal)
                            for k,v in pairs(self.NearGameList) do
                                if v.gameid == data.gameid then
                                    v.collected = false
                                    break
                                end
                            end
                            bee.setText(self.PageTip, _F("LAB_SAVE_LIMIT", self.CollectTotal .. " / " .. PlayerModel:getRecordNum()))
                        end
                    end)
                end
            })
            bee.logEvent("history-delete", data.gameid)
        end, true)
    end

    local PlayButton = self:find("PlayButton", item)
    bee.removeAllClick(PlayButton)
    bee.addClick(PlayButton, function()
        Net:post("/collCard/detail", {
            gameid= data.gameid,
            lang = LAN:getLanguage(),
        }, function(d)
            if 0 == d.code then
                local data = require("app.table.data.PKRecordData"):create(d.data, title)
                data:run()
                self:hideUI()
            end
        end)
        bee.logEvent("history-play", data.gameid)
    end, true)
end

--收藏记录
function P:saveData(data, CollectButton)
    Net:post("/collCard/update", {add_id = data.gameid, lang = LAN:getLanguage()}, function(d)
        if 0 == d.code then
            self.CollectSkip = self.CollectSkip + 1
            self.CollectTotal = self.CollectTotal + 1
            PlayerModel:setCurRecord(self.CollectTotal)
            data.collected = not data.collected
            self:refreshCollectButton(CollectButton, data.collected)
            table.insert(self.CollectList, 1, data)
        end
    end)
end

--更换收藏
function P:changeReplay(removeId, newData, CollectButton)
    Net:post("/collCard/update", {del_id = removeId, add_id = newData.gameid, lang = LAN:getLanguage()}, function(d)
        if 0 == d.code then
            for k,v in pairs(self.CollectList) do
                if v.gameid == removeId then
                    table.remove(self.CollectList, k)
                    break
                end
            end

            newData.collected = not newData.collected
            self:refreshCollectButton(CollectButton, newData.collected)
            table.insert(self.CollectList, 1, newData)
        end
    end)
end

--刷新历史牌局收藏按钮
function P:refreshCollectButton(CollectButton, sw)
    self:find("ingame_replay_button_collect_on", CollectButton):SetActive(sw)
    self:find("ingame_replay_button_collect_off", CollectButton):SetActive(not sw)
end

--筛选类型
function P:filterType(type, keepPos)
    local cacheList = {}
    if self.InNear then
        cacheList = self.NearGameList
        self.SaveNearType = type
    elseif self.InCollect then
        cacheList = self.CollectList
        self.SaveCollectType = type
    end

    local list = {}
    if type == REPLAY_GAME_TYPE.All then
        list = cacheList
    else
        local typeList = self.ReplayTypeDic[type]
        for _,v in pairs(cacheList) do
            if table.keyof(typeList, v.game_type) then
                table.insert(list, v)
            end
        end
    end

    bee.setText(self.FilterText, _T(self.ReplayTypeLabDic[type]))
    local noData = table.nums(list) == 0
    self.NoDataTip:SetActive(noData)
    self.ScrollBar:SetActive(not noData)
    if not keepPos then
        self.List:moveToYItem(1, false)
    end
    -- table.sort(list, function(a, b)  return a.game_start_time > b.game_start_time end)
    self.List:setDatas(list)
end

function P:onScrolling()
    if self.ReplayScroll.verticalNormalizedPosition < 0 then
        if self.InNear and table.nums(self.NearGameList) < self.NearTotal then
            Net:post("collCard/recentlyCardList", {skip = self.NearSkip, lang = LAN:getLanguage()}, function(data)
                if 0 == data.code then
                    self.NearSkip = self.NearSkip + table.nums(data.list)
                    if data.list then
                        for _,v in pairs(data.list) do
                            table.insert(self.NearGameList, v)
                        end
                    end
                    if self.InNear then
                        self:filterType(self.SaveNearType, true)
                    end 
                end
            end)
        end
        if self.InCollect and table.nums(self.CollectList) < PlayerModel:getCurRecord() then
            Net:post("collCard/list", {skip = self.CollectSkip, lang = LAN:getLanguage()}, function(data)
                self.CollectSkip = self.CollectSkip + table.nums(data.list)
                if 0 == data.code then
                    if data.list then
                        for _,v in pairs(data.list) do
                            table.insert(self.CollectList, v)
                        end
                    end
                    self:filterType(self.SaveCollectType, true)
                end
            end)
        end
    end
end

return P