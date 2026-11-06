local P = class("IngameReplay", UiFullView)

------------------ 回放的玩法类型 ------------------
REPLAY_GAME_TYPE = {
    All = 1,
    Poker = 2,
    Omaha = 3,
    AllInPoker = 4,
    SNG = 5,
    MTT = 6,
    Friend = 7,
    FriendOmaha = 8,
    FriendSNG = 9,
}

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local LeftTop = self:find("LeftTop", AnimRoot)
    local Tab = self:find("Left/TAB", AnimRoot)
    local Center = self:find("Center", AnimRoot)
    local Bottom = self:find("Bottom", AnimRoot)

    self.Tabs = {
        self:find("TabToggle/Tab01Toggle", Tab),
        self:find("TabToggle/Tab02Toggle", Tab),
    }

    self.ReplayList = self:find("IngameReplayList", Center)
    self.ReplayScroll = self.ReplayList:GetComponent("ScrollRect")
    self.ReplayScroll.onValueChanged:AddListener(function() self:onScrolling() end)
    self.ScrollBar = self:find("ScrollBar", Center)
    self.Item = self:find("Item", self.ReplayList)
    self.Item:SetActive(false)
    self.PageTip = self:find("Text", Bottom)
    self.NoDataTip = self:find("Empty", Center)

    local Refresh = self:find("Refresh", Center)
    self.RefreshButton = self:find("RefreshButton", Refresh)
    self.Filter = self:find("Filter", Refresh)

    bee.addClick(self:find("CloseButton", LeftTop), function()
        self:hideUI()
    end)
    
    bee.addClick(self.RefreshButton, function() self:reReqData() end)

    self.List = UiListEx:create(self.ReplayList)
    self.List:setWidth(260)
    self.List:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.List:setRefreshFunc(function(data, item)
        self:refreshItem(data, item)
    end)
    
    self._filterType = {
        REPLAY_GAME_TYPE.All,
        REPLAY_GAME_TYPE.All,
    }
    self._viewIndex = 1
    
    for k, v in ipairs(self.Tabs) do
        bee.onCheck(v, function(isOn)
            if isOn and not self._watiStart then
                self._viewIndex = k
                self.Filter:setSelectIdx(self._filterType[k])
            end
        end)
    end
    
    self.NearGameList = {}
    self.CollectList = {}
    
    self.NearTotal = 0
    self.CollectTotal = 0

    self.ReplayTypeDic = {
        [REPLAY_GAME_TYPE.Poker] = {GAME_GAME_TYPE.LOBBY_HOLDEM_GAME, GAME_GAME_TYPE.TRAINING_HOLDEM_GAME},
        [REPLAY_GAME_TYPE.Omaha] = {GAME_GAME_TYPE.LOBBY_OMAHA_GAME, GAME_GAME_TYPE.TRAINING_OMAHA_GAME},
        [REPLAY_GAME_TYPE.AllInPoker] = {GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN},
        [REPLAY_GAME_TYPE.SNG] = {GAME_GAME_TYPE.SNG_HOLDEM_GAME, GAME_GAME_TYPE.SNG_OMAHA_GAME, GAME_GAME_TYPE.SNG_TRAIN_GAME},
        [REPLAY_GAME_TYPE.MTT] = {GAME_GAME_TYPE.MTT_HOLDEM_GAME},
        [REPLAY_GAME_TYPE.Friend] = {GAME_GAME_TYPE.FRIEND_HOLDEM_GAME},
        [REPLAY_GAME_TYPE.FriendOmaha] = {GAME_GAME_TYPE.FRIEND_OMAHA_GAME},
        [REPLAY_GAME_TYPE.FriendSNG] = {GAME_GAME_TYPE.FRIEND_SNG_GAME},
    }
    self.ReplayTypeLabDic = {
        [REPLAY_GAME_TYPE.All] = _T("LAB_FRIROOM_034"),
        [REPLAY_GAME_TYPE.Poker] = _T("LAB_POKER_GAME"),
        [REPLAY_GAME_TYPE.Omaha] = _T("LAB_OMAHA"),
        [REPLAY_GAME_TYPE.AllInPoker] = _T("LAB_ALLIN_01"),
        [REPLAY_GAME_TYPE.SNG] = _T("LAB_TOURNAMENT_SNG"),
        [REPLAY_GAME_TYPE.MTT] = _T("LAB_TOURNAMENT_MTT"),
        [REPLAY_GAME_TYPE.Friend] = GF.getGameTypeName(GAME_GAME_TYPE.FRIEND_HOLDEM_GAME, true),
        [REPLAY_GAME_TYPE.FriendOmaha] = GF.getGameTypeName(GAME_GAME_TYPE.FRIEND_OMAHA_GAME, true),
        [REPLAY_GAME_TYPE.FriendSNG] = GF.getGameTypeName(GAME_GAME_TYPE.FRIEND_SNG_GAME, true),
    }

    self.Filter = UiFilterBox:create(self.Filter, self:find("FilterArea", self.Filter), self.node)
    self.Filter:setDatas(self.ReplayTypeLabDic)
    self.Filter:setSelectFunc(function(idx, data)
        self._filterType[self._viewIndex] = idx
        self:refreshList()
    end)
end

function P:onShow()
    self._scheme = DecorationModel:getCurScheme()
    self.NoDataTip:SetActive(false)
    self.ScrollBar:SetActive(true)

    if self._params and self._params.record then
        self._filterType[RecordDataModel.showIndex] = RecordDataModel.showType
        if 1 == RecordDataModel.showIndex then
            bee.setCheck(self.Tabs[1], true, true)
            self:refreshList()
        else
            bee.setCheck(self.Tabs[2], true, true)
        end
        self.Filter:setSelectIdx(RecordDataModel.showType)
    else
        bee.setCheck(self.Tabs[1], true, true)
        self:refreshList()
    end

    -- 任务进度-查看牌局回放
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.CardDeck)

    bee.logEvent("history-lobby")
end

function P:refreshList()
    RecordDataModel.showIndex = self._viewIndex
    RecordDataModel.showType = self._filterType[self._viewIndex]
    if 1 == self._viewIndex then
        RecordDataModel:fetchRecentList(self.ReplayTypeDic[self._filterType[self._viewIndex]], function(ok, list, total)
            if ok then
                self.NearGameList = {}
                self.NearTotal = total
                if list then
                    for k, v in ipairs(list) do
                        self.NearGameList[k] = v
                    end
                end
                self:filterType(self._filterType[self._viewIndex])
            end
        end)
        bee.setText(self.PageTip, _F("LAB_PLAYBACK3", PlayerModel:getRecentHistoryLimit()))
    else
        RecordDataModel:fetchCollectList(self.ReplayTypeDic[self._filterType[self._viewIndex]], function(ok, list, total)
            if ok then
                self.CollectList = {}
                if list then
                    for k, v in ipairs(list) do
                        self.CollectList[k] = v
                    end
                end
                
                self.CollectTotal = total
                PlayerModel:setCurRecord(self.CollectTotal)
                self:filterType(self._filterType[self._viewIndex])
                bee.setText(self.PageTip, _F("LAB_SAVE_LIMIT", string.format("%s / %s", self.CollectTotal, PlayerModel:getRecordNum())))
            end
        end)
        bee.setText(self.PageTip, _F("LAB_SAVE_LIMIT", string.format("%s / %s", PlayerModel:getCurRecord(), PlayerModel:getRecordNum())))
    end
end

--刷新数据
function P:reReqData()
    self.List:moveToYItem(1, false)
    RecordDataModel:markRecentDirty()
    RecordDataModel:markCollectDirty()
    self:refreshList()
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
    -- local scheme = DecorationModel:getCurScheme()
    local d = tpl_card_back[DecorationModel:getCurCardBack(self._scheme)]
    for i = 1, 5 do
        if data.cards[i] and data.cards[i] > 0 then
            bee.setIcon(ImageCards[i], GF.getCardImageByCode(data.cards[i], self._scheme))
        else
            bee.setIcon(ImageCards[i], d.image)
        end
    end
    local title = GameModel:getReplayTitle(data)
    bee.setText(self:find("TextTitle", item), title)
    
    local TextAdd, TextDec = self:find("TextAdd", item), self:find("TextDec", item)
    local TextCardType
    self:find("ingame_replay_lose", item):SetActive(data.profit < 0)
    self:find("ingame_replay_win", item):SetActive(data.profit > 0)
    self:find("ingame_replay_draw", item):SetActive(data.profit == 0)
    if data.profit >= 0 then
        bee.setText(self:find("ingame_replay_win/TextNum", item), "+" .. _N2(data.profit))
        
        self:find("ingame_replay_card_type_02", item):SetActive(true)
        self:find("ingame_replay_card_type_01", item):SetActive(false)
        TextCardType = self:find("ingame_replay_card_type_02/TextCardType", item)
    else
        bee.setText(self:find("ingame_replay_lose/TextNum", item), "-" .. _N2(-data.profit))
        
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
    CollectButton:SetActive(1 == self._viewIndex)
    if 1 == self._viewIndex then
        self:refreshCollectButton(CollectButton, data.collected)
        bee.removeAllClick(CollectButton)
        bee.addClick(CollectButton, function()
            if data.collected then
                RecordDataModel:removeCollect(data.gameid, function(ok)
                    if ok then
                        self:refreshCollectButton(CollectButton, data.collected)
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
                    GameModel:saveReplay(data.gameid, function(ok, removeId)
                        if ok then
                            self:changeReplay(removeId, data, CollectButton)
                        end
                    end)
                else
                    self:saveData(data, CollectButton)
                end
            end
        end)
    end

    local DeleteButton = self:find("DeleteButton", item)
    DeleteButton:SetActive(2 == self._viewIndex)
    if 2 == self._viewIndex then
        bee.removeAllClick(DeleteButton)
        bee.addClick(DeleteButton, function()
            UiManager:showTip({
                text = _T("LAB_DEL_PLAYBACK_TIP") .. "\n" .. title,
                onSure = function()
                    RecordDataModel:removeCollect(data.gameid, function(ok)
                        if ok then
                            self.List:removeData(data)
                            table.removebyvalue(self.CollectList, data)
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
        RecordDataModel:fetchGameDetail(data.gameid, function(ok, detail)
            if ok then
                local data = require("app.table.data.PKRecordData"):create(detail, title)
                data.listType = 2 == self._viewIndex and "collect" or "recent"
                data:run()
                RecordDataModel.verticalNormalizedPosition = self.ReplayScroll.verticalNormalizedPosition
                self:hideUI()
            end
        end)
        bee.logEvent("history-play", data.gameid)
    end, true)
    
    local EditButton = self:find("EditButton", item)
    if data.remark and data.remark ~= "" then
        bee.setText(self:find("TextRemark", item), data.remark)
    else
        bee.setText(self:find("TextRemark", item), _T("LAB_GAME_081"))
    end
    self:find("TextRemark", item):SetActive(2 == self._viewIndex)
    self:find("ingame_replay_bg_edit_01", item):SetActive(2 == self._viewIndex)
    EditButton:SetActive(2 == self._viewIndex)
    bee.addClick(EditButton, function()
        UiManager:showUI("IngameReplayEdit", {data = data, scheme = self._scheme})
    end, true)
end

--收藏记录
function P:saveData(data, CollectButton)
    RecordDataModel:addCollect(data.gameid, function(ok)
        if ok then
            self:refreshCollectButton(CollectButton, data.collected)
            table.insert(self.CollectList, 1, data)
        end
    end)
end

--更换收藏
function P:changeReplay(removeId, newData, CollectButton)
    for k,v in pairs(self.CollectList) do
        if v.gameid == removeId then
            table.remove(self.CollectList, k)
            break
        end
    end
    self:refreshCollectButton(CollectButton, newData.collected)
    table.insert(self.CollectList, 1, newData)
end

--刷新历史牌局收藏按钮
function P:refreshCollectButton(CollectButton, sw)
    self:find("ingame_replay_button_collect_on", CollectButton):SetActive(sw)
    self:find("ingame_replay_button_collect_off", CollectButton):SetActive(not sw)
end

--筛选类型
function P:filterType(type, keepPos)
    local cacheList = 1 == self._viewIndex and self.NearGameList or self.CollectList
    
    if type then
        self._filterType[self._viewIndex] = type
    end

    local noData = table.nums(cacheList) == 0
    self.NoDataTip:SetActive(noData)
    self.ScrollBar:SetActive(not noData)

    self.List:setDatas(cacheList)
    if self._params and self._params.record then
        self._params.record = nil
        if RecordDataModel.verticalNormalizedPosition then
            self.ReplayScroll.verticalNormalizedPosition = RecordDataModel.verticalNormalizedPosition
        end
    else
        if not keepPos then
            self.List:moveToYItem(1, false)
        end
    end
end

function P:onScrolling()
    if self.ReplayScroll.verticalNormalizedPosition < 0 then
        if 1 == self._viewIndex and RecordDataModel:hasMoreRecent() then
            RecordDataModel:fetchMoreRecent(function(ok, newList, hasMore)
                if ok then
                    if newList then
                        for _,v in pairs(newList) do
                            table.insert(self.NearGameList, v)
                        end
                    end
                    if 1 == self._viewIndex then
                        self:filterType(self._filterType[self._viewIndex], true)
                    end 
                end
            end)
        end
        if 2 == self._viewIndex and RecordDataModel:hasMoreCollect() then
            RecordDataModel:fetchMoreCollect(function(ok, newList, hasMore)
                if ok then
                    if newList then
                        for _,v in pairs(newList) do
                            table.insert(self.CollectList, v)
                        end
                    end
                    self:filterType(self._filterType[self._viewIndex], true)
                end
            end)
        end
    end
end

function P:evt_ReplayRemarkChanged()
    self.List:refreshShowingUi()
end

return P