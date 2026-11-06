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

    self.QuickByButton = self:find("RightTop/Buttons/QuickByButton", self.AnimRoot)
    self.LimitPackageButton = self:find("RightTop/Buttons/LimitPackageButton", self.AnimRoot)

    self._filters = {
        {id = 1, name = _T("LAB_TOURNAMENT_8")},
        {id = 2, name = _T("LAB_TOURNAMENT_SNG")},
        {id = 3, name = _T("LAB_TOURNAMENT_MTT")},
    }

    for k, v in ipairs(self.Tabs) do
        bee.addValueChanged(v, function(isOn)
            if isOn and self:isShow() then
                self._MttItemImgs = {}
                self:showView(k)
                bee.logEvent("tournament-tabs", k)
		        Game:playSound("ui_tab_switch_1")
            end
        end)
    end

    -- self.curStatusList = {}

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

    bee.addClick(self:find("InfoButton", self.Tabs[2]), function()
        UiManager:showUI("TournamentSNGRules")
        bee.logEvent("tournament-sng-rule")
    end)

    bee.addClick(self:find("InfoButton", self.Tabs[3]), function()
        UiManager:showUI("TournamentMTTRules")
        bee.logEvent("tournament-mtt-rule")
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
        if TournamentModel:isMttData(data) then
		    return CU.GameObject.Instantiate(self.ItemMTT)
        end
		return CU.GameObject.Instantiate(self.Item)
	end)
	self.ListMy:setRefreshFunc(function(data, item)
        if TournamentModel:isMttData(data) then
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

    self._MttItemImgs = {}
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
            local c = ObjectPool:getCls(obj)
            c:setParams({game_type = GameModel.selectRoomGameType})
            obj.transform:SetParent(self.GalaAddition.transform, false)
            obj.transform.localPosition = bee.v3zero
        end
    end

    if self._params and self._params.jump and self._params.jump.sub_page then
        local index = self._params.jump.sub_page[1]
        bee.setCheck(self.Tabs[index])
        self:showView(index)
    elseif self._params and self._params.kind then
        bee.setCheck(self.Tabs[self._params.kind])
        self:showView(self._params.kind)
    else
        local index = LocalStore:getIntegerForKey("TOURNAMENT_LOBBY_LAST_SHOW_INDEX_" .. PlayerModel:getUid(), 2)
        bee.setCheck(self.Tabs[index])
        self:showView(index)
    end

    if self._params and self._params.tour_id then
        self.tour_id = self._params.tour_id
    end

    QuickByModel:addButtonItem(self.uiName, self.QuickByButton)
    QuickByModel:addLimitButtonItem(self.uiName, self.LimitPackageButton)

    local i, iSNG = 1, 1
    self:schedule(1, function()
        if 1 == self._showIndex then
            self.ListMy:refreshShowingUi()
            i = i + 1
            if i % 10 == 0 then
                self:reqBriefInfo()
            end
        elseif 2 == self._showIndex then
            self.ListSNG:refreshShowingUi()
            iSNG = iSNG + 1
            if iSNG % 10 == 0 then
                self:refreshSNGList()
            end
        elseif 3 == self._showIndex then
            self.ListMTT:refreshShowingUi()
            i = i + 1
            if i % 10 == 0 then
                self:reqBriefInfo()
            end
        end
    end)
end

function P:reqBriefInfo()
    local ids = nil
    if 1 == self._showIndex then
        ids = {}
        for _, v in ipairs(TournamentModel.dataLists[TournamentModel.LIST_TYPE.My] or {}) do
            if v.isMtt then
                ids[#ids + 1] = v.tour_id
            end
        end
        if #ids == 0 then
            return
        end
    end
    TournamentModel:reqGetMttTourBriefInfoREQ(ids, function(ret)
        if bee.isNull(self.node) then
            return
        end
        if 1 == self._showIndex then
            -- self.ListMy:removeDataByFunc(function(data) return data.tour_status == TOUR_STATUS.Finished end)
            self.ListMy:refreshShowingUi()
            self.Empty:SetActive(self.ListMy:getDatasCount() == 0)
        elseif 3 == self._showIndex then
            self.ListMTT:removeDataByFunc(function(data) return data.tour_status == TOUR_STATUS.Finished end)
            self.ListMTT:refreshShowingUi()
            self.Empty:SetActive(self.ListMTT:getDatasCount() == 0)
        end
    end, self._showIndex)
end

function P:showView(index)
    self._showIndex = index or 1
    for i, view in ipairs(self.Views) do
        view:SetActive(i == index)
    end
    -- self.curStatusList = {}

    if 1 == index then
        self:refreshMyList()
    elseif 2 == index then
        self:refreshSNGList()
    else
        self:refreshMTTList()
    end
    
    LocalStore:setIntegerForKey("TOURNAMENT_LOBBY_LAST_SHOW_INDEX_" .. PlayerModel:getUid(), index)
end

function P:refreshMyList()
    bee.setText(self.FilterText, self._filters[self._myFilterIndex or 1].name)

    self._historyDatas = nil
    TournamentModel:reqTourList(TournamentModel.LIST_TYPE.My, function(datas)
        if bee.isNull(self.node) then
            return
        end
        if self._myFilterIndex == TournamentModel.HISTORY_TYPE.All then
            self._myDatas = datas
        else
            self._myDatas = {}
            for _, v in ipairs(datas) do
                if self._myFilterIndex == TournamentModel.HISTORY_TYPE.SNG and v.isSng then
                    table.insert(self._myDatas, v)
                elseif self._myFilterIndex == TournamentModel.HISTORY_TYPE.MTT and v.isMtt then
                    table.insert(self._myDatas, v)
                end
            end
        end
        self:_refreshMyList()

        if self._historyDatas then
            self:_refreshMyList(self._historyDatas)
        end
    end)
    if not bee.isCheck(self.CheckToggle) then
        self:refreshHistoryList()
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
    
    for k, v in ipairs(self._myDatas) do
        table.insert(datas, v)
    end
    if appendData then
        for k, v in ipairs(appendData) do
            table.insert(datas, v)
        end
    end

    self.ListMy:setDatas(datas)
    self.Empty:SetActive(self.ListMy:getDatasCount() == 0)
end

function P:refreshSNGList()
    TournamentModel:reqTourList(TournamentModel.LIST_TYPE.SNG, function(datas)
        if bee.isNull(self.node) then
            return
        end
        table.sort(datas, function(a, b)
            if nil == a.isCanSign then
                a.isCanSign = TournamentModel:isCanSign(a.sign_item_list) or a.tour_status == TOUR_STATUS.Register
            end
            if nil == b.isCanSign then
                b.isCanSign = TournamentModel:isCanSign(b.sign_item_list) or b.tour_status == TOUR_STATUS.Register
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

        if self.tour_id then
            for _,v in pairs(datas) do
                if self.tour_id == v.tour_id then
                    UiManager:showUI("TournamentSNGDetails", {data = v})
                    self.tour_id = nil
                end
            end
        end
    end)
    self.Empty:SetActive(self.ListSNG:getDatasCount() == 0)
end

function P:refreshMTTList()
    TournamentModel:reqTourList(TournamentModel.LIST_TYPE.MTT, function(datas)
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
            if a.mtt_start_time ~= b.mtt_start_time then
                return a.mtt_start_time < b.mtt_start_time
            end
            if a.sort_value ~= b.sort_value then
                return a.sort_value < b.sort_value
            end
            if a.byin_chips ~= b.byin_chips then
                return a.byin_chips < b.byin_chips
            end
            return a.tour_id < b.tour_id
        end)
        self.ListMTT:setDatas(datas)
        self.Empty:SetActive(#datas == 0)
    end)
        
    self.Empty:SetActive(self.ListMTT:getDatasCount() == 0)
end

function P:_refreshItem(data, item)
    local Ani_root = self:find("Ani_root", item)

    local signItem, itemData = TournamentModel:getSignItem(data)
    local BuyIn = self:find("BuyIn", Ani_root)
    bee.removeAllClick(BuyIn)
    if signItem then
        self:find("BuyIn/icon_10100001", Ani_root):SetActive(true)
        bee.setIcon(self:find("BuyIn/icon_10100001", Ani_root), tpl_props[signItem.item_id].icon)
        TournamentModel:setByinText(self:find("BuyIn/TextByin", Ani_root), signItem, TournamentModel:isUnregister(data))
        bee.addClick(BuyIn, function()
            UiManager:showUI("CommonItemTip", {data = itemData, target = BuyIn})
        end, true)
    else
        self:find("BuyIn/icon_10100001", Ani_root):SetActive(false)
        TournamentModel:setByinText(self:find("BuyIn/TextByin", Ani_root), nil)
    end

    local curItem = nil
    for i = 0, 5 do
        if i == data.style_id then
            local LabelItem = self:find("Item" .. i, Ani_root)
            LabelItem:SetActive(true)
            bee.setText(self:find("TextName", LabelItem), _T(data.tour_name))
            curItem = LabelItem
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

    if not data.reward_img or "" == data.reward_img then
        self:find("ImageIcon", Ani_root):SetActive(false)
        if curItem then
            self:find("Icon", curItem):SetActive(true) 
        end
    else
        local imageIcon = self:find("ImageIcon", Ani_root)
        imageIcon:SetActive(true)
        if imageIcon.activeInHierarchy then
            if self._MttItemImgs[item] ~= data.reward_img then
                self._MttItemImgs[item] = data.reward_img
                bee.setIcon(imageIcon, "Common[common_blank]")
            end
            bee.getDownloadImage(imageIcon, data.reward_img)
            if curItem then
                self:find("Icon", curItem):SetActive(false)
            end
        end
    end
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

    -- if self.curStatusList[data.tour_id] == nil then
    --     self.curStatusList[data.tour_id] = data.tour_status
    -- else
    --     if self._showIndex == 2 and data.tour_status == TOUR_STATUS.Inprocess and self.curStatusList[data.tour_id] ~= TOUR_STATUS.Inprocess then
    --         self.curStatusList[data.tour_id] = data.tour_status
    --         Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid})
    --     end
    -- end
    if data.tour_status == TOUR_STATUS.Unregister or data.tour_status == TOUR_STATUS.Register then
        bee.setText(self:find("Players/TextPlayerNum", Ani_root), "" .. data.cur_sign_num .. "/" .. data.seat_num)
    else
        bee.setText(self:find("Players/TextPlayerNum", Ani_root), "" .. data.cur_sign_num)
    end

    local isLock = data.level > PlayerModel:getCurLevel()
    self:find("BackButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Inprocess)
    -- self:find("EnterButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Register)
    self:find("CancelButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Register)
    self:find("ObserveButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Losed)
    self:find("RegisterButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Unregister)
    self:find("DetailButton", Ani_root):SetActive(not isLock and data.tour_status == TOUR_STATUS.Finished)
    self:find("LockButton", Ani_root):SetActive(isLock)

    if isLock then
        bee.setText(self:find("LockButton/TextUnlock", Ani_root), _F("LAB_LEVEL_TEXT_1", data.level))
    elseif data.tour_status == TOUR_STATUS.Inprocess then
        bee.addClick(self:find("BackButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            if not bee.checkCd("EnterRoomREQ", 2) then
                return
            end
            Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid}, function ()
                TournamentModel:setMatchingSngInfo(0, 0, {}, 0)
            end)
        end, true)
    elseif data.tour_status == TOUR_STATUS.Register then
        -- bee.addClick(self:find("EnterButton", Ani_root), function()
        --     Game:playSound("ui_button_confirm")
        --     if data.roomid == 0 or not bee.checkCd("EnterRoomREQ", 2) then
        --         return
        --     end
        --     Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid})
        -- end, true)
        self:find("ImageTag", Ani_root):SetActive(true)
        bee.setText(self:find("ImageTag/TextTag", Ani_root), _T("LAB_TOURNAMENT_MTT_INFO2"))
        bee.addClick(self:find("CancelButton", Ani_root), function ()
            Game:playSound("ui_button_confirm")
            if data.roomid == 0 or not bee.checkCd("SngCancelSignREQ", 2) then
                return
            end
            TournamentModel:reqSngCancelSign(data.roomid, data.game_type)
        end, true)
    elseif data.tour_status == TOUR_STATUS.Unregister then
        bee.addClick(self:find("RegisterButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            local signItem, itemData = TournamentModel:getSignItem(data)
            if signItem and signItem.item_num > ItemModel:getItemNumById(signItem.item_id) then
                UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[signItem.item_id].name)))
                if signItem.item_id == GPropId.Gold then
                    QuickByModel:checkShowView(GAME_GAME_TYPE.TOURNAMENT)
                end
                return
            end
            if not bee.checkCd("SngSignREQ", 2) then
                return
            end
            TournamentModel:reqSngSign(data, signItem and signItem.item_id or 0)
        end, true)
    elseif data.tour_status == TOUR_STATUS.Losed then
        bee.addClick(self:find("ObserveButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid, is_observer = true, uid_being_observed = PlayerModel:getUid()})
        end, true)
    elseif data.tour_status == TOUR_STATUS.Finished then
        bee.addClick(self:find("DetailButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("TournamentSNGDetails", {data = data})
        end, true)
    end
    bee.addClick2(item, function()
        UiManager:showUI("TournamentSNGDetails", {data = data})
    end, true)
end

function P:refreshMttItem(data, item)
    self:_refreshItem(data, item)

    local Ani_root = self:find("Ani_root", item)

    local Time = self:find("Time", Ani_root)
    Time:SetActive(false)
    self:find("Tab", Ani_root):SetActive(data.player_status ~= MTT_PLAYER_STATUS.Unregister)
    self:find("Tab/Eliminated", Ani_root):SetActive(data.tour_status ~= TOUR_STATUS.Finished and data.player_status == MTT_PLAYER_STATUS.Losed)
    self:find("Tab/Registered", Ani_root):SetActive(data.tour_status ~= TOUR_STATUS.Finished and data.player_status == MTT_PLAYER_STATUS.Register)
    self:find("Tab/Rank", Ani_root):SetActive(data.my_rank and data.my_rank > 0)
    if data.my_rank and data.my_rank > 0 then
        bee.setText(self:find("Tab/Rank/Text", Ani_root), "# " .. data.my_rank)
    end

    local isLock = data.level > PlayerModel:getCurLevel()
    local isCanBack = TournamentModel:isCanEnterMTT(data)
    local isCanRegister = TournamentModel:isCanRegisterMTT(data)
    local isCanUnregister = TournamentModel:isCanUnregisterMTT(data)
    local isShowDetail = TournamentModel:isCanShowDetailMTT(data)
    local isShowEnter = TournamentModel:isCanObserveMTT(data)
    local isLimit = TournamentModel:isUnregister(data) and data.sign_start_time <= bee.getServerTime() and data.sign_end_time >= bee.getServerTime() and data.cur_sign_num >= data.max_player_num and TournamentModel:isInSignStatus(data)

    local ct = bee.getServerTime()

    local Times = {
        self:find("Time1", Time),
        self:find("Time2", Time),
        self:find("Time3", Time),
    }
    for _, v in ipairs(Times) do
        v:SetActive(false)
    end

    if data.mtt_start_time <= ct and data.tour_status == TOUR_STATUS.Unopen then
        data.tour_status = TOUR_STATUS.Inprocess
    end

    if data.tour_status == TOUR_STATUS.Finished then
        bee.setText(self:find("Players/TextPlayerNum", Ani_root), "" .. data.cur_sign_num)
    elseif data.tour_status == TOUR_STATUS.Inprocess or data.tour_status == TOUR_STATUS.Losed then
        bee.setText(self:find("Players/TextPlayerNum", Ani_root), "" .. data.left_players .. "/" .. data.cur_sign_num)
    else
        bee.setText(self:find("Players/TextPlayerNum", Ani_root), "" .. data.cur_sign_num .. "/" .. data.max_player_num)
    end
    
    if data.mtt_start_time > ct then
        Time:SetActive(true)
        Times[1]:SetActive(true)
        bee.setText(self:find("Time1/TextTime", Time), TimeHelp:getDateTimeStr(data.mtt_start_time))
    elseif data.tour_status == TOUR_STATUS.Inprocess then
        Time:SetActive(true)
        if data.player_status == MTT_PLAYER_STATUS.Losed then
            Times[3]:SetActive(true)
            
            bee.setText(self:find("Time3/TextTitle", Time), _T("LAB_TOURNAMENT_SNG_INFO12"))
            bee.setText(self:find("Time3/TextTime", Time), TimeHelp:getTimeStr(ct - data.mtt_start_time))
        else
            Times[2]:SetActive(true)
            if TournamentModel:isUnregister(data) and isCanRegister then
                bee.setText(self:find("Time2/TextTitle", Time), _T("LAB_TOURNAMENT_MTT_INFO59"))
                bee.setText(self:find("Time2/TextTime", Time), TimeHelp:getTimeStr(data.sign_end_time - ct))
            else
                bee.setText(self:find("Time2/TextTitle", Time), _T("LAB_TOURNAMENT_SNG_INFO12"))
                bee.setText(self:find("Time2/TextTime", Time), TimeHelp:getTimeStr(ct - data.mtt_start_time))
            end
        end
    elseif data.tour_status == TOUR_STATUS.Finished then
        Time:SetActive(true)
        Times[3]:SetActive(true)
        bee.setText(self:find("Time3/TextTitle", Time), _T("LAB_TOURNAMENT_MTT_INFO60"))
        bee.setText(self:find("Time3/TextTime", Time), TimeHelp:getDateTimeStr(data.mtt_start_time))
    elseif data.player_status == MTT_PLAYER_STATUS.Losed then
        Time:SetActive(true)
        Times[3]:SetActive(true)
        
        bee.setText(self:find("Time3/TextTitle", Time), _T("LAB_TOURNAMENT_SNG_INFO12"))
        bee.setText(self:find("Time3/TextTime", Time), TimeHelp:getTimeStr(ct - data.mtt_start_time))
    end
    
    self:find("BackButton", Ani_root):SetActive(not isLock and isCanBack)
    self:find("EnterButton", Ani_root):SetActive(not isLock and isShowEnter and not isCanRegister)
    self:find("RegisterButton", Ani_root):SetActive(not isLock and isCanRegister and data.mtt_start_time >= ct)
    self:find("DelayRegisterButton", Ani_root):SetActive(not isLock and isCanRegister and data.mtt_start_time < ct)
    self:find("UnRegisterButton", Ani_root):SetActive(not isLock and isCanUnregister)
    self:find("DetailButton", Ani_root):SetActive(not isLock and (isShowDetail or isLimit) and not isShowEnter)
    self:find("LockButton", Ani_root):SetActive(isLock)

    self:find("Seen", Ani_root):SetActive(data.open_observer)
    
    if isShowEnter then
        bee.addClick(self:find("EnterButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid, is_observer = true}, function(msg)
                if msg.code ~= 0 then
                    self:reqBriefInfo()
                end
            end)
        end, true)
    end

    if isLock then
        bee.setText(self:find("LockButton/TextUnlock", Ani_root), _F("LAB_LEVEL_TEXT_1", data.level))
    elseif isCanBack then
        bee.addClick(self:find("BackButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            if not bee.checkCd("EnterRoomREQ", 2) then
                return
            end
            Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid}, function(msg)
                if msg.code ~= 0 then
                    self:reqBriefInfo()
                end
            end)
        end, true)
    elseif isCanRegister then
        local onBtRegister = function(autoEnter)
            Game:playSound("ui_button_confirm")
            local signItem, itemData = TournamentModel:getSignItem(data)
            if signItem and signItem.item_num > ItemModel:getItemNumById(signItem.item_id) then
                UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[signItem.item_id].name)))
                if signItem.item_id == GPropId.Gold then
                    QuickByModel:checkShowView(GAME_GAME_TYPE.TOURNAMENT)
                end
                return
            end
            if not bee.checkCd("MttSignREQ", 2) then
                return
            end
            TournamentModel:reqMttSign(data, signItem and signItem.item_id or 0, function()
                bee.checkCd("EnterRoomREQ", 0.5)
                if not bee.isNull(self.node) then
                    -- self.ListMTT:refreshShowingUi()
                    self:refreshMttItem(data, item)
                    if autoEnter then
                        Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid})
                    end
                end
            end)
        end
        bee.addClick(self:find("RegisterButton", Ani_root), function()
            onBtRegister()
        end, true)
        bee.addClick(self:find("DelayRegisterButton", Ani_root), function()
            onBtRegister(true)
        end, true)
    elseif isCanUnregister then
        bee.addClick(self:find("UnRegisterButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            TournamentModel:reqMttCancelSign(data, function()
                if not bee.isNull(self.node) then
                    -- self.ListMTT:refreshShowingUi()
                    self:refreshMttItem(data, item)
                end
            end)
        end, true)
    elseif self:find("DetailButton", Ani_root).activeSelf then
        bee.addClick(self:find("DetailButton", Ani_root), function()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("TournamentMTTDetails", {data = data})
        end, true)
    end
    bee.addClick2(item, function()
        UiManager:showUI("TournamentMTTDetails", {data = data})
    end, true)
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

function P:evt_SngSign()
    -- bee.checkCd("EnterRoomREQ", 2)
    if not bee.isNull(self.node) then
        self:refreshSNGList()
    end
end

function P:evt_CancelSngSign()
    if 1 == self._showIndex then
        self:refreshMyList()
    elseif 2 == self._showIndex then
        self:refreshSNGList()
    end
end

function P:evt_SngWaitingOtherEnterBRC(msg)
    if 1 == self._showIndex then
        self:refreshMyList()
    elseif 2 == self._showIndex then
        self:refreshSNGList()
    end
end

function P:evt_MttCancelSignREQ(msg)
    if 1 == self._showIndex then
        self.ListMy:refreshShowingUi()
    elseif 2 == self._showIndex then
        self.ListSNG:refreshShowingUi()
    else
        self.ListMTT:refreshShowingUi()
    end
end

function P:evt_refreshTopInfo()
    bee.invoke(self.GoldItem, "setCount", _N2(PlayerModel:getGold()))
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

function P:evt_MTT_CANCEL(msg)
    if 1 == self._showIndex then
        local items = self.ListMy:getDatas()
        local datas = {}
        for k, v in ipairs(items) do
            if v.data.tour_id ~= msg.tour_id then
                table.insert(datas, v.data)
            end
        end
        self.ListMy:setDatas(datas)
    elseif 2 == self._showIndex then
    else
        local items = self.ListMTT:getDatas()
        local datas = {}
        for k, v in ipairs(items) do
            if v.data.tour_id ~= msg.tour_id then
                table.insert(datas, v.data)
            end
        end
        self.ListMTT:setDatas(datas)
    end
end

function P:hideUI()
	P.super.hideUI(self)
	QuickByModel:hideButton(self.QuickByButton)
    QuickByModel:hideLimitButton(self.LimitPackageButton)

end

return P