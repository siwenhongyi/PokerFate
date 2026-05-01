local P = class("TournamentLobby", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.FilterMask = self:find("FilterMask", self.AnimRoot)
    self.FilterMask:SetActive(false)

    self.GoldItem = self:find("RightTop/GoldItem", self.AnimRoot)
    self.tab = self:find("tab", self.Center)
    self.GalaAddition = self:find("GalaAddition", self.tab)
    self.Tabs = {
        self:find("MyButton", self.tab),
        self:find("SNGButton", self.tab),
        self:find("MTTButton", self.tab),
    }

    self.Views = {
        self:find("My", self.Center),
        self:find("SNG", self.Center),
        self:find("MTT", self.Center),
    }

    self.Item = self:find("Item", self.Views[2])
    self.Item:SetActive(false)
    self.ItemMTT = self:find("ItemMTT", self.Views[3])
    self.ItemMTT:SetActive(false)
    self.Empty = self:find("Empty", self.Center)

    self.CheckToggle = self:find("CheckToggle", self.Views[1])
    self.Filter = self:find("Filter", self.Views[1])
    self.Filter.transform:SetParent(self.FilterMask.transform, true)
    self.shop_musice_item_filter_button_arrow = self:find("FilterButton/shop_musice_item_filter_button_arrow", self.Views[1])
    self.shop_musice_item_filter_button_arrow_2 = self:find("FilterButton/shop_musice_item_filter_button_arrow_2", self.Views[1])
    self.FilterText = self:find("FilterButton/Text", self.Views[1])

    self.QuickByButton = self:find("RightTop/QuickByButton", self.AnimRoot)

    self._filters = {
        {id = 1, name = _T("LAB_TOURNAMENT_8")},
        {id = 2, name = _T("LAB_TOURNAMENT_SNG")},
        {id = 3, name = _T("LAB_TOURNAMENT_MTT")},
    }

    for k, v in ipairs(self.Tabs) do
        bee.addValueChanged(v, function(isOn)
            if isOn and self:isShow() then
                self:showView(k)
                bee.logEvent("tournament-tabs", k)
		        Game:playSound("ui_tab_switch_1")
            end
        end)
    end

    bee.addValueChanged(self.CheckToggle, function(isOn)
        LocalStore:setBoolForKey("TOURNAMENT_LOBBY_MY_RUNNING_ONLY", isOn)
        self:_refreshMyList()
        if isOn then
            bee.logEvent("tournament-mine-inprogress")
        else
            self:refreshHistoryList()
        end
    end)

    bee.addClick(self:find("LeftTop/BackButton", self.AnimRoot), function()
        self:hideUI()
    end)

    self.tournament_lobby_info_01 = self:find("tournament_lobby_title_zh/tournament_lobby_info_01", self.Center)
    bee.addClick(self.tournament_lobby_info_01, function()
        -- UiManager:showUI("CommonRules", {text = _T("LAB_TOURNAMENT_SNG_RULE1"), title = _T("LAB_TOURNAMENT_SNG_RULE2")})
        UiManager:showUI("TournamentSNGRules")
        bee.logEvent("tournament-sng-rule")
    end)

    bee.addClick(self:find("RefreshButton", self.Views[1]), function()
        self:showView(self._showIndex)
    end)

    bee.addClick(self:find("FilterButton", self.Views[1]), function()
        self.FilterMask:SetActive(true)
        if not self._initFilter then
            self._initFilter = true
            self:initFilter()
        else
            for k, v in ipairs(self._FilterItems) do
                local filterData = self._filters[k]
                self:find("tournament_lobby_filter_list_01", v):SetActive(self._myFilterIndex ~= filterData.id)
                self:find("common_panel_back_filter_list_01", v):SetActive(self._myFilterIndex == filterData.id)
            end
        end
        self.shop_musice_item_filter_button_arrow:SetActive(false)
        self.shop_musice_item_filter_button_arrow_2:SetActive(true)
    end)

    bee.addClick2(self.FilterMask, function()
        self.FilterMask:SetActive(false)
        self.shop_musice_item_filter_button_arrow:SetActive(true)
        self.shop_musice_item_filter_button_arrow_2:SetActive(false)
    end)

    self.ListMy = UiListEx:create(self:find("Item2List", self.Views[1]))
	self.ListMy:setCreateFunc(function(data)
        if data.mtt_start_time then
		    return CU.GameObject.Instantiate(self.ItemMTT)
        end
		return CU.GameObject.Instantiate(self.Item)
	end)
	self.ListMy:setRefreshFunc(function(data, item)
        if data.mtt_start_time then
            self:refreshMttItem(data, item)
            return
        end
		self:refreshListItem(data, item)
	end)
    self.ListMy:setScrollToBottomFunc(function()
        if self._showIndex ~= 1 or not bee.checkCd("TOURNAMENT_LOBBY_REQ_NEXT_HISTORY_LIST", 0.5) then
            return
        end
        local showRunningOnly = bee.isCheck(self.CheckToggle)
        if showRunningOnly then
            return
        end

        TournamentModel:reqNextHistoryList(self._myFilterIndex, function(datas)
            if bee.isNull(self.node) then
                return
            end
            -- for k, v in ipairs(datas) do
            --     table.insert(self._myDatas, v)
            -- end
            self:_refreshMyList(datas)
        end)
    end)
	self.ListMy:setWidth(230)
	self.ListMy:setSpacing(10)

    self.ListSNG = UiListEx:create(self:find("Item1List", self.Views[2]))
	self.ListSNG:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item)
	end)
	self.ListSNG:setRefreshFunc(function(data, item)
		self:refreshListItem(data, item)
	end)
	self.ListSNG:setWidth(230)
	self.ListSNG:setSpacing(10)

    self.ListMTT = UiListEx:create(self:find("Item1List", self.Views[3]))
	self.ListMTT:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.ItemMTT)
	end)
	self.ListMTT:setRefreshFunc(function(data, item)
		self:refreshMttItem(data, item)
	end)
	self.ListMTT:setWidth(230)
	self.ListMTT:setSpacing(10)

    -- 任务-查看赛事界面
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.Tournament)
end

function P:onShow()
    bee.invoke(self.GoldItem, "setItemId", GPropId.Gold)
    self:evt_refreshTopInfo()

    GameModel.selectRoomGameType = GAME_GAME_TYPE.TOURNAMENT
    self._myFilterIndex = 1
    bee.setCheck(self.CheckToggle, nil, LocalStore:getBoolForKey("TOURNAMENT_LOBBY_MY_RUNNING_ONLY", false))

    self:removeAllChildren(self.GalaAddition)
    if ThemeModel:isHaveAddtion(GAME_GAME_TYPE.SNG_HOLDEM_GAME) then
        local obj = ThemeModel:createAddtionButton()
        if not bee.isNull(obj) then
            obj.transform:SetParent(self.GalaAddition.transform, false)
            obj.transform.localPosition = bee.v3zero
        end
    end

    if self._params and self._params.kind then
        bee.setCheck(self.Tabs[self._params.kind])
        self:showView(self._params.kind)
    else
        bee.setCheck(self.Tabs[2])
        self:showView(2)
    end

    QuickByModel:addButtonItem(self.uiName, self.QuickByButton)
end

function P:showView(index)
    self._showIndex = index or 1
    for i, view in ipairs(self.Views) do
        view:SetActive(i == index)
    end

    if 1 == index then
        self:refreshMyList()
    elseif 2 == index then
        self:refreshSNGList()
    else
        self:refreshMTTList()
    end
    self.tournament_lobby_info_01:SetActive(2 == index)
end

function P:refreshMyList()
    bee.setText(self.FilterText, self._filters[self._myFilterIndex or 1].name)

    self._historyDatas = nil
    if self._myFilterIndex == TournamentModel.HISTORY_TYPE.MTT then
        self.ListMy:setDatas({})
    else
        TournamentModel:reqTourList(TournamentModel.LIST_TYPE.My, function(datas)
            if bee.isNull(self.node) then
                return
            end
            self._myDatas = datas
            self:_refreshMyList()

            if self._historyDatas then
                self:_refreshMyList(self._historyDatas)
            end
        end)
        if not bee.isCheck(self.CheckToggle) then
            self:refreshHistoryList()
        end
    end
    self.Empty:SetActive(self.ListMy:getDatasCount() == 0)
end

function P:refreshHistoryList()
    TournamentModel:reqHistoryList(self._myFilterIndex, function(datas)
        if bee.isNull(self.node) then
            return
        end
        self._historyDatas = datas
        self:_refreshMyList(datas)
    end)
end

function P:_refreshMyList(appendData)
    if not self._myDatas then
        return
    end
    local datas = {}
    
    for k, v in ipairs(appendData or self._myDatas) do
        table.insert(datas, v)
    end
    
    if appendData then
        self.ListMy:append(datas)
    else
        self.ListMy:setDatas(datas)
    end
    self.Empty:SetActive(self.ListMy:getDatasCount() == 0)
end

function P:refreshSNGList()
    TournamentModel:reqTourList(TournamentModel.LIST_TYPE.SNG, function(datas)
        if bee.isNull(self.node) then
            return
        end
        table.sort(datas, function(a, b)
            if nil == a.isCanSign then
                a.isCanSign = TournamentModel:isCanSign(a.sign_item_list)
            end
            if nil == b.isCanSign then
                b.isCanSign = TournamentModel:isCanSign(b.sign_item_list)
            end
            if a.isCanSign ~= b.isCanSign then
                return a.isCanSign 
            end
            if a.sort_value ~= b.sort_value then
                return a.sort_value < b.sort_value
            end
            if a.byin_chips ~= b.byin_chips then
                return a.byin_chips < b.byin_chips
            end
            return a.tour_id < b.tour_id
        end)
        self.ListSNG:setDatas(datas)
        self.Empty:SetActive(#datas == 0)
        for _, v in ipairs(datas) do
            if GF.isTrainingGame(v.game_type) and not GuideManager:isInGuide() then
                GuideManager:startSystemGuide(14001, 0.5)
                break
            end
        end
    end)
    self.Empty:SetActive(self.ListSNG:getDatasCount() == 0)
end

function P:refreshMTTList()
    self.Empty:SetActive(false)
    -- TournamentModel:reqTourList(TournamentModel.LIST_TYPE.MTT, function(datas)
    --     if bee.isNull(self.node) then
    --         return
    --     end
        -- table.sort(datas, function(a, b)
        --     if a.byin_chips ~= b.byin_chips then
        --         return a.byin_chips < b.byin_chips
        --     end
        --     return a.tour_id < b.tour_id
        -- end)
    --     self.ListMTT:setDatas(datas)
    --     self.Empty:SetActive(#datas == 0)
    -- end)
    -- self.Empty:SetActive(self.ListMTT:getDatasCount() == 0)
end

function P:_refreshItem(data, item)
    local Ani_root = self:find("Ani_root", item)

    local is_mtt = data.mtt_start_time ~= nil
    local signItem, itemData = nil, nil
    local BuyIn = self:find("BuyIn", Ani_root)
    bee.removeAllClick(BuyIn)
    if #data.sign_item_list > 0 then
        for k, v in ipairs(data.sign_item_list) do
            itemData = ItemModel:getItem(v.item_id, true)
            if itemData.num >= v.item_num or k == #data.sign_item_list then
                self:find("BuyIn/icon_10100001", Ani_root):SetActive(true)
                bee.setIcon(self:find("BuyIn/icon_10100001", Ani_root), tpl_props[v.item_id].icon)
                TournamentModel:setByinText(self:find("BuyIn/TextByin", Ani_root), v, data.tour_status == TOUR_STATUS.Unregister)
                signItem = v
                bee.addClick(BuyIn, function()
                    UiManager:showUI("CommonItemTip", {data = itemData, target = BuyIn})
                end, true)
                break
            end
        end
    else
        self:find("BuyIn/icon_10100001", Ani_root):SetActive(false)
        TournamentModel:setByinText(self:find("BuyIn/TextByin", Ani_root), nil)
    end
    if data.tour_status == TOUR_STATUS.Unregister or data.tour_status == TOUR_STATUS.Register then
        bee.setText(self:find("Players/TextPlayerNum", Ani_root), "" .. data.cur_sign_num .. "/" .. data.seat_num)
    else
        bee.setText(self:find("Players/TextPlayerNum", Ani_root), "" .. data.cur_sign_num)
    end

    for i = 0, 5 do
        if i == data.style_id then
            local LabelItem = self:find("Item" .. i, Ani_root)
            LabelItem:SetActive(true)
            bee.setText(self:find("TextName", LabelItem), _T(data.tour_name))
        else
            self:find("Item" .. i, Ani_root):SetActive(false)
        end
    end

    if data.event_reward_list and #data.event_reward_list > 0 then
        local BgReward = self:find("BgReward", Ani_root)
        BgReward:SetActive(true)
        self:removeAllChildren(BgReward)
        if data.event_id and ThemeModel:isActivityOpen(data.event_id) then
            local obj = ThemeModel:createRewardTag(data.event_id)
            if not bee.isNull(obj) then
                obj.transform:SetParent(BgReward.transform, false)
                obj.transform.localPosition = bee.v3zero
                bee.setText(self:find("TextCount", obj), _N(data.event_reward_list[1].item_num))
            end
        end
    else
        self:find("BgReward", Ani_root):SetActive(false)
    end

    local isLock = data.level > PlayerModel:getCurLevel()
    self:find("BackButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Inprocess)
    self:find("EnterButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Register)
    self:find("RegisterButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Unregister)
    self:find("DetailButton", Ani_root):SetActive(not isLock and (data.tour_status == TOUR_STATUS.Finished or data.tour_status == TOUR_STATUS.Losed))
    self:find("LockButton", Ani_root):SetActive(isLock)
    if isLock then
        bee.setText(self:find("LockButton/TextUnlock", Ani_root), _F("LAB_LEVEL_TEXT_1", data.level))
    elseif data.tour_status == TOUR_STATUS.Inprocess then
        bee.addClick(self:find("BackButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            if not bee.checkCd("EnterRoomREQ", 2) then
                return
            end
            Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid})
        end, true)
    elseif data.tour_status == TOUR_STATUS.Register then
        bee.addClick(self:find("EnterButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            if data.roomid == 0 or not bee.checkCd("EnterRoomREQ", 2) then
                return
            end
            Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid})
        end, true)
    elseif data.tour_status == TOUR_STATUS.Unregister then
        bee.addClick(self:find("RegisterButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            if signItem and signItem.item_num > ItemModel:getItemNumById(signItem.item_id) then
                UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[signItem.item_id].name)))
                if signItem.item_id == GPropId.Gold then
                    QuickByModel:checkShowView(GAME_GAME_TYPE.TOURNAMENT)
                end
                return
            end
            if is_mtt then
                if not bee.checkCd("MttSignREQ", 2) then
                    return
                end
                TournamentModel:reqMttSign(data, signItem and signItem.item_id or 0, function()
                    bee.checkCd("EnterRoomREQ", 2)
                    self.ListMTT:refreshShowingUi()
                end)
            else
                if not bee.checkCd("SngSignREQ", 2) then
                    return
                end
                TournamentModel:reqSngSign(data, signItem and signItem.item_id or 0, function()
                    bee.checkCd("EnterRoomREQ", 2)
                    self.ListSNG:refreshShowingUi()
                end)
            end
        end, true)
    elseif data.tour_status == TOUR_STATUS.Finished or data.tour_status == TOUR_STATUS.Losed then
        bee.addClick(self:find("DetailButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("TournamentSNGDetails", {data = data})
        end, true)
    end
    bee.addClick2(item, function()
        UiManager:showUI("TournamentSNGDetails", {data = data})
    end, true)
end

function P:refreshListItem(data, item)
    if GF.isTrainingGame(data.game_type) then
        item.name = "ItemTrain"
    end

    self:_refreshItem(data, item)

    local Ani_root = self:find("Ani_root", item)
    if data.my_rank and data.my_rank > 0 then
        self:find("ImageTag", Ani_root):SetActive(true)
        bee.setText(self:find("ImageTag/TextTag", Ani_root), "# " .. data.my_rank)
    else
        self:find("ImageTag", Ani_root):SetActive(false)
    end
end

function P:refreshMttItem(data, item)
    self:_refreshItem(data, item)

    local Ani_root = self:find("Ani_root", item)
    local Time = self:find("Time", Ani_root)
    if data.my_rank and data.my_rank > 0 then
        self:find("Tag", Ani_root):SetActive(true)
        self:find("Tag/Eliminated", Ani_root):SetActive(false)
        self:find("Tag/Registered", Ani_root):SetActive(false)
        self:find("Tag/Rank", Ani_root):SetActive(true)
        bee.setText(self:find("Tag/Rank/Text", Ani_root), "# " .. data.my_rank)

        Time:SetActive(false)
    elseif data.tour_status == TOUR_STATUS.Register then
        self:find("Tag", Ani_root):SetActive(true)
        self:find("Tag/Eliminated", Ani_root):SetActive(false)
        self:find("Tag/Registered", Ani_root):SetActive(true)
        self:find("Tag/Rank", Ani_root):SetActive(false)
    elseif data.tour_status == TOUR_STATUS.Losed then
        self:find("Tag", Ani_root):SetActive(true)
        self:find("Tag/Eliminated", Ani_root):SetActive(true)
        self:find("Tag/Registered", Ani_root):SetActive(false)
        self:find("Tag/Rank", Ani_root):SetActive(false)
    else
        self:find("Tag", Ani_root):SetActive(false)
    end

    if data.mtt_start_time > bee.getServerTime() then
        Time:SetActive(true)
        self:find("Time1/TextTime"):SetActive(true)
        self:find("Time2/TextTime"):SetActive(false)
        self:find("Time3/TextTime"):SetActive(false)

        bee.setText(self:find("Time1/TextTime"), TimeHelp:getDateTimeStr(data.mtt_start_time))
    elseif data.tour_status == TOUR_STATUS.Inprocess then
        Time:SetActive(true)
        self:find("Time1/TextTime"):SetActive(false)
        self:find("Time2/TextTime"):SetActive(true)
        self:find("Time3/TextTime"):SetActive(false)

        bee.setText(self:find("Time2/TextTime"), TimeHelp:getTimeStr(bee.getServerTime() - data.mtt_start_time))
    elseif data.tour_status == TOUR_STATUS.Losed then
        Time:SetActive(true)
        self:find("Time1/TextTime"):SetActive(false)
        self:find("Time2/TextTime"):SetActive(false)
        self:find("Time3/TextTime"):SetActive(true)

        bee.setText(self:find("Time3/TextTime"), TimeHelp:getTimeStr(bee.getServerTime() - data.mtt_start_time))
    end
end

function P:initFilter()
    self._FilterItems = {}
    local FilterItem = self:find("FilterItem", self.Filter)
    FilterItem:SetActive(false)
    for k, v in ipairs(self._filters) do
        local item = CU.GameObject.Instantiate(FilterItem, self.Filter.transform, false)
        item:SetActive(true)
        self._FilterItems[k] = item
        self:find("tournament_lobby_filter_list_01", item):SetActive(self._myFilterIndex ~= v.id)
        self:find("common_panel_back_filter_list_01", item):SetActive(self._myFilterIndex == v.id)
        bee.setText(self:find("tournament_lobby_filter_list_01/Text", item), v.name)
        bee.setText(self:find("common_panel_back_filter_list_01/Text", item), v.name)
        bee.addClick(item, function()
            if v.id ~= self._myFilterIndex then
                self._myFilterIndex = v.id
                self:refreshMyList()
            end
            self.FilterMask:SetActive(false)

            self.shop_musice_item_filter_button_arrow:SetActive(true)
            self.shop_musice_item_filter_button_arrow_2:SetActive(false)
        end)
    end
end

function P:evt_ItemChangeRSP(msg)
    if 1 == self._showIndex then
        self.ListMy:refreshShowingUi()
    elseif 2 == self._showIndex then
        self.ListSNG:refreshShowingUi()
    else
        self.ListMTT:refreshShowingUi()
    end
end

function P:evt_refreshTopInfo()
    bee.invoke(self.GoldItem, "setCount", _N(PlayerModel:getGold()))
    if 1 == self._showIndex then
        self.ListMy:refreshShowingUi()
    elseif 2 == self._showIndex then
        self.ListSNG:refreshShowingUi()
    else
        self.ListMTT:refreshShowingUi()
    end
end

function P:evt_sng_not_available()
    self:showView(self._showIndex)
end

function P:hideUI()
	P.super.hideUI(self)
	QuickByModel:hideButton(self.QuickByButton)
end

return P