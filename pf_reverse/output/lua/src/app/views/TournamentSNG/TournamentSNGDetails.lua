local P = class("TournamentSNGDetails", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)

    self.GoldItem = self:find("RightTop/GoldItem", self.AnimRoot)
    
    self.EnterButton = self:find("EnterButton", self.Center)
    self.RegisterButton = self:find("RegisterButton", self.Center)
    self.UnRegisterButton = self:find("UnRegisterButton", self.Center)
    self.LockButton = self:find("LockButton", self.Center)

    self.RewardButton = self:find("RewardButton", self.Center)


    local tournament_lobby_frame_01 = self:find("tournament_lobby_frame_01", self.Center)
    self.tournament_lobby_frame_01 = tournament_lobby_frame_01
    self.BuyIn = self:find("BuyIn", tournament_lobby_frame_01)
    self.TextByin = self:find("BuyIn/TextByin", tournament_lobby_frame_01)
    self.icon_10100001 = self:find("BuyIn/icon_10100001", tournament_lobby_frame_01)
    self.TextMyRank = self:find("TextMyRank", self.Center)

    local tournament_sng_details_bg = self:find("tournament_sng_details_bg", self.Center)
    self.TextPoint = self:find("TextPoint", tournament_sng_details_bg)
    self.ItemPoint = self:find("ItemPoint", tournament_sng_details_bg)
    self.TextReward = self:find("TextReward", tournament_sng_details_bg)
    self.BgItemReward = self:find("BgItemReward", tournament_sng_details_bg)
    self.ItemReward = self:find("ItemReward", tournament_sng_details_bg)
    self.ItemTitle = self:find("ItemTitle", tournament_sng_details_bg)
    self.TextStartClips = self:find("TextStartClips", tournament_sng_details_bg)
    self.ItemReward:SetActive(false)
    self.ItemTitle:SetActive(false)
    
    self.TextPlayerCount = self:find("TextPlayerCount", tournament_sng_details_bg)
    self.TextBlind = self:find("TextBlind", tournament_sng_details_bg)
    self.TextJoinReward = self:find("TextJoinReward", tournament_sng_details_bg)
    self.BgJoinReward = self:find("BgJoinReward", tournament_sng_details_bg)

    self.BgRewardTag = self:find("BgRewardTag", tournament_sng_details_bg)

    self.Item = self:find("Item", tournament_sng_details_bg)
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
        UiManager:showUI("TournamentSNGRules", {data = self._data})
        bee.logEvent("tournament-sng-rule")
    end)
    bee.addClick(self:find("title1/Blind Structure/InfoButton", tournament_sng_details_bg), function()
        UiManager:showUI("TournamentBlindStructure", {data = self._data.blind_list})
    end)

    bee.addClick(self.RewardButton, function()
        UiManager:showUI("TournamentSNGlist", {data = self._data.rank_list, champion_points = self._data.champion_points})
    end)
    bee.addClick(self.EnterButton, function()
        Game:playSound("ui_button_confirm")
        if not bee.checkCd("EnterRoomREQ", 2) then
            return
        end
        Net:sendReq("pb.EnterRoomREQ", {roomid = self._data.roomid})
    end)
    bee.addClick(self.RegisterButton, function()
        Game:playSound("ui_button_confirm")
        -- if not self.signItem or not self.item then
        --     UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[self.signItem.item_id].name)))
        --     return
        -- end
        if self.signItem and self.signItem.item_num > ItemModel:getItemNumById(self.signItem.item_id) then
            UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[self.signItem.item_id].name)))
            return
        end
        if not bee.checkCd("SngSignREQ", 2) then
            return
        end
        TournamentModel:reqSngSign(self._listData, self.signItem and self.signItem.item_id or 0, function()
            if bee.isNull(self.node) then
                return
            end
            self:refreshUI()
        end)
    end)
    bee.addClick(self.UnRegisterButton, function()
    end)
end

function P:onShow()
    bee.invoke(self.GoldItem, "setItemId", GPropId.Gold)
    self:evt_refreshTopInfo()

    self._listData = self._params.data
    self._data = self._params.data
    Net:sendReq("pb.TourDetailInfoREQ", {
        setid = self._listData.setid,
        tour_id = self._listData.tour_id, 
        roomid = self._listData.roomid, 
        game_type = self._listData.game_type, 
        lang = LAN:getLanguage()
    })

    self:refreshUI()
end

function P:refreshUI()
    local isHaveDetail = nil ~= self._detailData and self._detailData.self_sng_info.my_rank > 0
    if isHaveDetail then
        if self._detailData.self_sng_info.sign_item and self._detailData.self_sng_info.sign_item.item_id > 0 then
            self.signItem = self._detailData.self_sng_info.sign_item
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
    TournamentModel:setByinText(self.TextByin, self.signItem, self._data.tour_status == TOUR_STATUS.Unregister)
    
    if (self._data.win_exp and self._data.win_exp > 0) or (self._data.bond_add and self._data.bond_add > 0) then
        self.TextJoinReward:SetActive(false)
        self.BgJoinReward:SetActive(true)
        local Item1 = self:find("Item1", self.BgJoinReward)
        Item1:SetActive(false)
        if self._Items then
            for _, v in ipairs(self._Items) do
                CU.GameObject.Destroy(v)
            end
        end
        self._Items = {}
        if self._data.win_exp and self._data.win_exp > 0 then
            local item = CU.GameObject.Instantiate(Item1, self.BgJoinReward.transform, false)
            item:SetActive(true)
            self._Items[#self._Items + 1] = item
            PropItem:create(item, {id = GPropId.ExpSNG, num = self._data.win_exp, format = {VipModel:getExpTournament()}}): bindTips()
        end
        if self._data.bond_add and self._data.bond_add > 0 then
            local item = CU.GameObject.Instantiate(Item1, self.BgJoinReward.transform, false)
            item:SetActive(true)
            self._Items[#self._Items + 1] = item
            PropItem:create(item, {id = GPropId.BondSNG, num = self._data.bond_add, format = {VipModel:getFriendshipTournament()}}): bindTips()
        end
    else
        self.TextJoinReward:SetActive(true)
        self.BgJoinReward:SetActive(false)
    end

    if self._data.blind_list then
        local blind = self._data.blind_list[1]
        bee.setText(self.TextBlind, "1-" .. self._data.blind_list[#self._data.blind_list].blind_level)
        self:removeAllChildren(self.BgItemReward)
        if self._data.total_reward > 0 then
            self.TextReward:SetActive(true)
            if isHaveDetail or self._data.tour_status == TOUR_STATUS.Inprocess or self._data.tour_status == TOUR_STATUS.Losed then
                bee.setText(self.TextReward, _N1(self._data.total_reward))
            else
                bee.setText(self.TextReward, _F("LAB_TOURNAMENT_SNG_INFO6", _N1(self._data.total_reward)))
            end
        elseif self._data.rank_list and #self._data.rank_list > 0 and #self._data.rank_list[1].reward_item_list > 0 then
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
        -- bee.setText(self.TextPoint, _N(self._data.champion_points))
        if self._data.champion_points > 0 then
            self.TextPoint:SetActive(false)
            self.ItemPoint:SetActive(true)
            PropItem:create(self.ItemPoint, {id = GPropId.ChampionPoints, num = self._data.champion_points}): bindTips()
        else
            self.TextPoint:SetActive(true)
            self.ItemPoint:SetActive(false)
        end
    else
        self.TextPoint:SetActive(true)
        self.ItemPoint:SetActive(false)
    end
    if self._data.tour_status == TOUR_STATUS.Unregister or self._data.tour_status == TOUR_STATUS.Register then
        bee.setText(self.TextPlayerCount, "" .. self._data.cur_sign_num .. "/" .. self._data.seat_num)
    else
        bee.setText(self.TextPlayerCount, "" .. self._data.cur_sign_num)
    end

    for i = 0, 5 do
        if i == self._data.style_id then
            local LabelItem = self:find("Item" .. i, self.Item)
            LabelItem:SetActive(true)
            bee.setText(self:find("TextName", LabelItem), _T(self._data.tour_name))
        else
            self:find("Item" .. i, self.Item):SetActive(false)
        end
    end

    local isLock = self._data.level > PlayerModel:getCurLevel()
    self.EnterButton:SetActive(not isLock and self._data.tour_status == TOUR_STATUS.Inprocess)
    self.RegisterButton:SetActive(not isLock and self._data.tour_status == TOUR_STATUS.Unregister)
    self.UnRegisterButton:SetActive(not isLock and self._data.tour_status == TOUR_STATUS.Register)
    self.RewardButton:SetActive(not isLock and self._data.tour_status == TOUR_STATUS.Finished)
    self.LockButton:SetActive(isLock)

    if isLock then
        bee.setText(self:find("TextUnlock", self.LockButton), _F("LAB_LEVEL_TEXT_1", self._data.level))
    end

    self.TextMyRank:SetActive(isHaveDetail)
    if isHaveDetail then
        bee.setText(self.TextMyRank, self._detailData.self_sng_info.my_rank)
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
end

function P:evt_TourDetailInfoRSP(msg)
    local byin_chips = self._data.byin_chips
    self._data = msg.sng_info
    self._detailData = msg
    self._data.level = msg.level
    self._data.byin_chips = byin_chips
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

return P