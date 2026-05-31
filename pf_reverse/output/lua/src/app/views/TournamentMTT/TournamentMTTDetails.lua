local P = class("TournamentMTTDetails", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)

    self.GoldItem = self:find("RightTop/GoldItem", self.AnimRoot)
    
    self.Buttons = self:find("Buttons", self.Center)
    self.ClosedButton = self:find("ClosedButton", self.Buttons)
    self.BackButton = self:find("BackButton", self.Buttons)
    self.EnterButton = self:find("EnterButton", self.Buttons)
    self.RegisterButton = self:find("RegisterButton", self.Buttons)
    self.DelayRegisterButton = self:find("DelayRegisterButton", self.Buttons)
    self.CancelButton = self:find("CancelButton", self.Buttons)
    self.LockButton = self:find("LockButton", self.Buttons)
    self.ToplimitButton = self:find("ToplimitButton", self.Buttons)
    self.EliminatedButton = self:find("EliminatedButton", self.Buttons)

    local LeftBottom = self:find("LeftBottom", self.Center)
    self.RankPrizesButton = self:find("RankPrizesButton", LeftBottom)
    self.RankButton  = self:find("RankButton ", LeftBottom)
    self.PrizesButton = self:find("PrizesButton", LeftBottom)


    local tournament_lobby_frame_01 = self:find("tournament_lobby_frame_01", self.Center)
    self.tournament_lobby_frame_01 = tournament_lobby_frame_01
    self.BuyIn = self:find("BuyIn", tournament_lobby_frame_01)
    self.TextByin = self:find("BuyIn/TextByin", tournament_lobby_frame_01)
    self.icon_10100001 = self:find("BuyIn/icon_10100001", tournament_lobby_frame_01)
    self.TextMyRank = self:find("TextMyRank", self.Center)

    local tournament_sng_details_bg = self:find("tournament_sng_details_bg", self.Center)
    self.TextBreakTime = self:find("TextBreakTime", tournament_sng_details_bg)
    self.TextSignCount = self:find("TextSignCount", tournament_sng_details_bg)
    self.TextSignTitle = self:find("title1/TextSignTitle", tournament_sng_details_bg)
    self.TextDelaySign = self:find("TextDelaySign", tournament_sng_details_bg)
    self.TextBlind = self:find("TextBlind", tournament_sng_details_bg)
    self.TextBlindTitle = self:find("title1/TextBlindTitle", tournament_sng_details_bg)
    self.TextBlindUpTime = self:find("TextBlindUpTime", tournament_sng_details_bg)
    self.TextExp = self:find("TextExp", tournament_sng_details_bg)
    self.BgItemExp = self:find("BgItemExp", tournament_sng_details_bg)
    self.TextReward = self:find("TextReward", tournament_sng_details_bg)
    self.BgItemReward = self:find("BgItemReward", tournament_sng_details_bg)
    self.ItemReward = self:find("ItemReward", tournament_sng_details_bg)
    self.ItemTitle = self:find("ItemTitle", tournament_sng_details_bg)
    self.TextStartClips = self:find("TextStartClips", tournament_sng_details_bg)
    self.ItemReward:SetActive(false)
    self.ItemTitle:SetActive(false)
    
    self.TextPlayerCount = self:find("TextPlayerCount", tournament_sng_details_bg)
    self.TextJoinReward = self:find("TextJoinReward", tournament_sng_details_bg)
    self.BgJoinReward = self:find("BgJoinReward", tournament_sng_details_bg)

    self.BgRewardTag = self:find("BgRewardTag", tournament_sng_details_bg)

    self.Item = self:find("Item", tournament_sng_details_bg)
    self.TextTime = self:find("TextTime", self.Item)
    self.TextStartTip = self:find("TextStartTip", self.Item)
    self.TextEndSign = self:find("TextEndSign", self.Item)
    -- 比赛状态 1进行中 2已结束
    self.Tabs = {
        self:find("Tab/Tab1", self.Item),
        self:find("Tab/Tab2", self.Item),
    }

    bee.addClick(self:find("LeftTop/BackButton", self.AnimRoot), function()
        self:hideUI()
    end)
    bee.addClick(self:find("LeftTop/InfoButton", self.AnimRoot), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("TournamentMTTRules", {data = self._data})
        bee.logEvent("tournament-mtt-rule")
    end)
    bee.addClick(self:find("common_button_info_06", self.TextBlindTitle), function()
        UiManager:showUI("TournamentBlindStructure", {data = self._data.blind_list, infoCb = function()
            UiManager:showUI("TournamentMTTpayout", {data = self._data})
        end})
    end)

    bee.addClick(self.RankPrizesButton, function()
        UiManager:showUI("TournamentMTTlist", {data = self._data})
    end)
    bee.addClick(self.RankButton, function()
        UiManager:showUI("TournamentMTTRanks", {data = self._data})
    end)
    bee.addClick(self.PrizesButton, function()
        UiManager:showUI("TournamentMTTPrizes", {data = self._data})
    end)
    bee.addClick(self.BackButton, function()
        Game:playSound("ui_button_confirm")
        if not bee.checkCd("EnterRoomREQ", 2) then
            return
        end
        Net:sendReq("pb.EnterRoomREQ", {roomid = self._data.roomid})
    end)
    bee.addClick(self.EnterButton, function()
        Game:playSound("ui_button_confirm")
        Net:sendReq("pb.EnterRoomREQ", {roomid = self._data.roomid, is_observer = true}, function(msg)
            if msg.code ~= 0 then
                self:reqBriefInfo()
            end
        end)
    end)
    bee.addClick(self.RegisterButton, function()
        self:onBtRegister()
    end)
    bee.addClick(self.DelayRegisterButton, function()
        self:onBtRegister(true)
    end)
    bee.addClick(self.CancelButton, function()
        TournamentModel:reqMttCancelSign(self._data, function()
            if bee.isNull(self.node) then
                return
            end
            self:refreshUI()
        end)
    end)
end

function P:onShow()
    bee.invoke(self.GoldItem, "setItemId", GPropId.Gold)
    self:evt_refreshTopInfo()

    self._listData = self._params and self._params.data
    self._data = self._params and self._params.data
    if not self._data then
        self._data = {
            tour_id = 0,
            tour_name = "Test",
            style_id = 3,
            sign_item_list = {},
            max_player_num = 20,
            cur_sign_num = 6,
            begin_chips = 7,
            blind_list = {{blind_level = 1, small_blind = 50, big_blind = 100, ante = 0, duration = 200}},
            total_reward = 9,
            roomid = 10,
            break_interval = 12,
            break_duration = 13,
            late_reg_level = 1,
            event_id = 0,
            event_reward_list = {},
            sign_end_time = bee.getServerTime() + 1000,

            tour_status = -1,
            sign_status = 1,
            player_status = 0,

            mtt_start_time = bee.getServerTime() + 500,
        }
    else
        Net:sendReq("pb.TourDetailInfoREQ", {
            setid = self._listData.setid,
            tour_id = self._listData.tour_id, 
            roomid = self._listData.roomid, 
            game_type = self._listData.game_type, 
            lang = LAN:getLanguage()
        })
    end
    bee.logEvent("tournament-detail", 2, self._data.tour_id)

    self:refreshUI()

    local i = 1
    self:schedule(1, function()
        self:refreshTime()
        self:refreshButtons()
        i = i + 1
        if i % 10 == 0 then
            self:reqBriefInfo()
        end
    end)
end

function P:reqBriefInfo()
    TournamentModel:reqGetMttTourBriefInfoREQ({self._data.tour_id}, function(ret)
        if bee.isNull(self.node) then
            return
        end
        self._data.cur_sign_num = ret.sign_num
        if ret.sign_status then
            self._data.sign_status = ret.sign_status
        end
        if ret.tour_status then
            self._data.tour_status = ret.tour_status
        end
        self:refreshPlayerNum()
        self:refreshBlindInfo()
    end)
end

function P:refreshUI()
    local isHaveDetail = nil ~= self._detailData and self._detailData.self_mtt_info.my_rank > 0
    if isHaveDetail then
        if self._detailData.self_mtt_info.sign_item and self._detailData.self_mtt_info.sign_item.item_id > 0 then
            self.signItem = self._detailData.self_mtt_info.sign_item
            self.item = ItemModel:getItem(self.signItem.item_id, true)
        end
        self.tournament_lobby_frame_01:SetActive(false)
    else
        self.tournament_lobby_frame_01:SetActive(true)
        if #self._data.sign_item_list > 0 then
            for k, v in ipairs(self._data.sign_item_list) do
                local item = ItemModel:getItem(v.item_id, true)
                if item.num >= v.item_num or k == #self._data.sign_item_list then
                    self.signItem = v
                    self.item = item
                    break
                end
            end
        end
    end
    bee.removeAllClick(self.BuyIn)
    if self.signItem then
        self.icon_10100001:SetActive(true)
        bee.setIcon(self.icon_10100001, tpl_props[self.signItem.item_id].icon)
        -- bee.setText(self.TextByin, _N(self.signItem.item_num))
        bee.addClick(self.BuyIn, function()
            UiManager:showUI("CommonItemTip", {data = self.item, target = self.BuyIn})
        end, true)
    else
        self.icon_10100001:SetActive(false)
        -- bee.setText(self.TextByin, _T("LAB_SHOP_COMMON_21"))
    end
    TournamentModel:setByinText(self.TextByin, self.signItem, self._data.player_status == MTT_PLAYER_STATUS.Unregister)
    
    -- if (self._data.win_exp and self._data.win_exp > 0) or (self._data.bond_add and self._data.bond_add > 0) then
    --     self.TextJoinReward:SetActive(false)
    --     self.BgJoinReward:SetActive(true)
    --     local Item1 = self:find("Item1", self.BgJoinReward)
    --     Item1:SetActive(false)
    --     if self._Items then
    --         for _, v in ipairs(self._Items) do
    --             CU.GameObject.Destroy(v)
    --         end
    --     end
    --     self._Items = {}
    --     if self._data.win_exp and self._data.win_exp > 0 then
    --         local item = CU.GameObject.Instantiate(Item1, self.BgJoinReward.transform, false)
    --         item:SetActive(true)
    --         self._Items[#self._Items + 1] = item
    --         PropItem:create(item, {id = GPropId.ExpSNG, num = self._data.win_exp, format = {VipModel:getExpTournament()}}): bindTips()
    --     end
    --     if self._data.bond_add and self._data.bond_add > 0 then
    --         local item = CU.GameObject.Instantiate(Item1, self.BgJoinReward.transform, false)
    --         item:SetActive(true)
    --         self._Items[#self._Items + 1] = item
    --         PropItem:create(item, {id = GPropId.BondSNG, num = self._data.bond_add, format = {VipModel:getFriendshipTournament()}}): bindTips()
    --     end
    -- else
    --     self.TextJoinReward:SetActive(true)
    --     self.BgJoinReward:SetActive(false)
    -- end

    if self._data.blind_list then
        local blind = self._data.blind_list[1]
        self:removeAllChildren(self.BgItemReward)
        if self._data.total_reward > 0 then
            self.TextReward:SetActive(true)
            bee.setText(self.TextReward, _N1(self._data.total_reward))
        elseif self._data.rank_list and #self._data.rank_list > 0 then
            self.TextReward:SetActive(false)
            for _, v in ipairs(self._data.rank_list[1].reward_item_list) do
                local item = nil
                if tpl_props[v.item_id].type == GPropKind.Title then
                    item = CU.GameObject.Instantiate(self.ItemTitle, self.BgItemReward.transform, false)
                else
                    item = CU.GameObject.Instantiate(self.ItemReward, self.BgItemReward.transform, false)
                end
                item:SetActive(true)
                PropItem:create(item, {id = v.item_id, num = v.item_num}): bindTips()
            end
        else
            self.TextReward:SetActive(true)
        end
        bee.setText(self.TextStartClips, _N(self._data.begin_chips))
        bee.setText(self.TextBlindUpTime, TimeHelp:getTimeLeftStr(blind.duration, true))
    else
        bee.setText(self.TextBlindUpTime, "--")
    end
    self:refreshBlindInfo()
    self:refreshPlayerNum()
    
    self:removeAllChildren(self.BgItemExp)
    local items = {}
    if self._data.win_exp and self._data.win_exp > 0 then
        table.insert(items, {id = GPropId.ExpSNG, num = self._data.win_exp, format = {VipModel:getExpTournament()}})
    end
    if self._data.bond_add and self._data.bond_add > 0 then
        table.insert(items, {id = GPropId.BondSNG, num = self._data.bond_add, format = {VipModel:getFriendshipTournament()}})
    end
    if #items > 0 then
        bee.setText(self.TextExp, "")
        GF.addItemsToParent(self.BgItemExp, self.ItemReward, items)
    else
        bee.setText(self.TextExp, "-")
    end
    bee.setText(self.TextDelaySign, _F("LAB_TOURNAMENT_MTT_INFO50", self._data.late_reg_level))
    if self._data.break_duration and self._data.break_duration > 0 then
        bee.setText(self.TextBreakTime, _F("LAB_TIME_MINUTES", self._data.break_interval / 60) .. "/" .. _F("LAB_TIME_MINUTES", self._data.break_duration / 60))
    else
        bee.setText(self.TextBreakTime, "--")
    end

    for i = 1, 5 do
        if i == self._data.style_id then
            local LabelItem = self:find("Item" .. i, self.Item)
            LabelItem:SetActive(true)
        else
            self:find("Item" .. i, self.Item):SetActive(false)
        end
    end
    bee.setText(self:find("TextName", self.Center), _T(self._data.tour_name))

    self.TextMyRank:SetActive(isHaveDetail)
    if isHaveDetail then
        bee.setText(self.TextMyRank, self._detailData.self_mtt_info.my_rank)
    end

    self.Tabs[1]:SetActive(self._data.tour_status == TOUR_STATUS.Inprocess or self._data.tour_status == TOUR_STATUS.Losed)
    self.Tabs[2]:SetActive(self._data.tour_status == TOUR_STATUS.Finished)
    
    if self._data.event_reward_list and #self._data.event_reward_list > 0 then
        self.BgRewardTag:SetActive(true)
        self:removeAllChildren(self.BgRewardTag)
        if self._data.event_id and ThemeModel:isActivityOpen(self._data.event_id) then
            local obj = ThemeModel:createRewardTag(self._data.event_id)
            if not bee.isNull(obj) then
                obj.transform:SetParent(self.BgRewardTag.transform, false)
                obj.transform.localPosition = bee.v3zero
                bee.setText(self:find("TextCount", obj), _N(self._data.event_reward_list[1].item_num))
            end
        end
    else
        self.BgRewardTag:SetActive(false)
    end

    self:refreshTime()
    self:refreshButtons()

    if self._data.level and self._data.level > PlayerModel:getCurLevel() then
        bee.setText(self:find("TextUnlock", self.LockButton), _F("LAB_LEVEL_TEXT_1", self._data.level))
    end
end

function P:refreshPlayerNum()
    if self._data.mtt_start_time > bee.getServerTime() then
        bee.setText(self.TextSignTitle, _T("LAB_TOURNAMENT_SNG_INFO3"))
        bee.setText(self.TextSignCount, "" .. self._data.cur_sign_num)
    else
        bee.setText(self.TextSignTitle, _T("LAB_TOURNAMENT_10"))
        bee.setText(self.TextSignCount, "" .. self._data.left_players .. "/" .. self._data.cur_sign_num)
    end
end

function P:refreshBlindInfo()
    if self._data.blind_list then
        if self._data.mtt_start_time < bee.getServerTime() then
            bee.setText(self.TextBlindTitle, _F("LAB_TOURNAMENT_MTT_INFO50", self._data.blind_level or 1))
            local blind = self._data.blind_list[self._data.blind_level] or self._data.blind_list[1]
            
            local sb = blind.small_blind
            local bb = blind.big_blind
            local ante = blind.ante
            if ante and ante > 0 then
                bee.setText(self.TextBlind, _F("{p1}/{p2} ({p3})", _N(sb), _N(bb), _N(ante)))
            else
                bee.setText(self.TextBlind, _N(sb) .. "/" .. _N(bb))
            end
        else
            bee.setText(self.TextBlindTitle, _T("LAB_TOURNAMENT_SNG_INFO2"))
            local blind = self._data.blind_list[1]
            bee.setText(self.TextBlind, "1-" .. self._data.blind_list[#self._data.blind_list].blind_level)
        end
    end
end

function P:refreshTime()
    local ct = bee.getServerTime()
    local dt = self._data.mtt_start_time - ct
    if self._data.tour_status == TOUR_STATUS.Finished then
         bee.setText(self.TextTime, TimeHelp:getDateTimeStr(self._data.mtt_start_time))
         bee.setText(self.TextStartTip, _T("LAB_TOURNAMENT_MTT_INFO60"))
         self.TextStartTip:SetActive(true)
         self.TextEndSign:SetActive(false)
    elseif dt >= 0 then
         bee.setText(self.TextTime, TimeHelp:getDateTimeStr(self._data.mtt_start_time))
         bee.setText(self.TextStartTip, _T("LAB_TOURNAMENT_MTT_INFO4"))
         self.TextStartTip:SetActive(true)
         self.TextEndSign:SetActive(false)
    else
        bee.setText(self.TextTime, TimeHelp:getTimeStr(-dt))
        if ct < self._data.sign_end_time and TournamentModel:isInSignStatus(self._data) then
            local dt2 = self._data.sign_end_time - ct
            bee.setText(self.TextStartTip, _F("LAB_TOURNAMENT_MTT_INFO3", math.ceil(dt2 / 60)))
            self.TextStartTip:SetActive(true)
            self.TextEndSign:SetActive(false)
        else
            self.TextStartTip:SetActive(false)
            self.TextEndSign:SetActive(true)
        end
    end
end

function P:refreshButtons()
    local isLock = self._data.level and self._data.level > PlayerModel:getCurLevel() or false
    local ct = bee.getServerTime()
    
    local isCanBack = TournamentModel:isCanEnterMTT(self._data)
    local isCanRegister = TournamentModel:isCanRegisterMTT(self._data)
    local isCanUnregister = TournamentModel:isCanUnregisterMTT(self._data)
    local isShowDetail = TournamentModel:isCanShowDetailMTT(self._data)
    local isShowEnter = TournamentModel:isCanObserveMTT(self._data)

    self.ClosedButton:SetActive(not isLock and not isCanBack and self._data.player_status == MTT_PLAYER_STATUS.Unregister and self._data.sign_end_time < ct)
    self.BackButton:SetActive(not isLock and isCanBack)
    self.RegisterButton:SetActive(not isLock and isCanRegister and self._data.mtt_start_time >= ct)
    self.DelayRegisterButton:SetActive(not isLock and isCanRegister and self._data.mtt_start_time < ct)
    self.CancelButton:SetActive(not isLock and isCanUnregister)
    self.LockButton:SetActive(isLock)
    local isLimit = TournamentModel:isUnregister(self._data) and self._data.sign_start_time <= bee.getServerTime() and self._data.sign_end_time >= bee.getServerTime() and self._data.cur_sign_num >= self._data.max_player_num and TournamentModel:isInSignStatus(self._data)
    self.ToplimitButton:SetActive(not isLock and isLimit)
    self.EliminatedButton:SetActive(not isLock and self._data.player_status == MTT_PLAYER_STATUS.Losed and not isShowEnter and self._data.tour_status ~= TOUR_STATUS.Finished)
    self.EnterButton:SetActive(not isLock and (isShowEnter or self.DelayRegisterButton.activeSelf or self.ClosedButton.activeSelf or self.ToplimitButton.activeSelf))
    
    self.RankPrizesButton:SetActive(not isLock and self._data.tour_status == TOUR_STATUS.Finished)
    self.RankButton:SetActive(not isLock and self._data.tour_status == TOUR_STATUS.Inprocess or self._data.tour_status == TOUR_STATUS.Losed)
    self.PrizesButton:SetActive(not isLock and self._data.tour_status ~= TOUR_STATUS.Finished)
end

function P:onBtRegister(autoEnter)
    Game:playSound("ui_button_confirm")
    
    if self.signItem and self.signItem.item_num > ItemModel:getItemNumById(self.signItem.item_id) then
        UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[self.signItem.item_id].name)))
        return
    end
    if not bee.checkCd("MttSignREQ", 2) then
        return
    end
    TournamentModel:reqMttSign(self._listData, self.signItem and self.signItem.item_id or 0, function()
        if bee.isNull(self.node) then
            return
        end
        self._data.player_status = self._listData.player_status
        self:refreshUI()
        if autoEnter then
            Net:sendReq("pb.EnterRoomREQ", {roomid = self._listData.roomid})
        end
    end)
end

function P:evt_TourDetailInfoRSP(msg)
    local oldData = self._data
    self._data = msg.mtt_info
    self._detailData = msg
    self._data.level = msg.level
    for k, v in pairs(oldData) do
        if not self._data[k] then
            self._data[k] = v
        end
    end
    self._data.player_status = msg.self_mtt_info.player_status
    self:refreshUI()
end

function P:evt_ItemChangeRSP(msg)
    self:refreshUI()
end

function P:evt_refreshTopInfo()
    bee.invoke(self.GoldItem, "setCount", _N(PlayerModel:getGold()))
    if self._data then
        self:refreshUI()
    end
end

function P:evt_sng_not_available()
    self:hideUIForce()
end

function P:evt_MTT_CANCEL(msg)
    if msg.tour_id == self._data.tour_id then
		if "" ~= msg.reason then
			local code = tonumber(msg.reason)
			if code then
				Net:onErrorCode({code = code})
			end
		end
        self:hideUI()
    end
end

return P