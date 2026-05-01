local P = class("TournamentSNGingame", UiDialog)

function P:onAwake()
    self.Right = self:find("AnimRoot/Right")
    self.SidePanel = self:find("SidePanel", self.Right)

    local Tabs = self:find("Tabs", self.SidePanel)

    self.Tabs = {
        self:find("DetailsButton", Tabs),
        self:find("RankButton", Tabs),
        self:find("BlindsButton", Tabs),
    }

    self.Views = {
        self:find("Details", self.SidePanel),
        self:find("Rank", self.SidePanel),
        self:find("Blinds", self.SidePanel),
    }

    self.TextBlind = self:find("TextBlind", self.Views[1])
    self.TextTime = self:find("TextTime", self.Views[1])
    self.TextBlindNext = self:find("TextBlindNext", self.Views[1])
    self.TextCurLevel = self:find("TextCurLevel", self.Views[1])
    self.TextBlindLimit = self:find("TextBlindLimit", self.Views[1])
    self.TextTitle = self:find("TextTitle", self.Views[1])

    self.TextRank = self:find("Iteam1/TextRank", self.Views[1])
    self.TextPlayerCount = self:find("Iteam1/TextPlayerCount", self.Views[1])
    self.TextByin = self:find("Iteam1/TextByin", self.Views[1])

    self.ItemPrizePool = self:find("Iteam2/Item1", self.Views[1])
    self.ItemTitle = self:find("Iteam2/ItemTitle", self.Views[1])
    self.BgItemReward = self:find("Iteam2/BgItemReward", self.Views[1])
    self.TextPoint = self:find("Iteam3/TextPoint", self.Views[1])
    self.ItemPoint = self:find("Iteam3/Item1", self.Views[1])
    self.ItemTitle:SetActive(false)

    self.Iteam4 = self:find("Iteam4", self.Views[1])

    self.RankItems = {
        self:find("Item1", self.Views[2]),
        self:find("Item2", self.Views[2]),
        self:find("Item3", self.Views[2]),
    }

    self.BlindList = self:find("BlindList", self.Views[3])
    self.Item1 = self:find("Item1", self.BlindList)
    self.Item1:SetActive(false)

    for k, v in ipairs(self.Tabs) do
        bee.onCheck(v, function(isOn)
            if isOn then
                self:showView(k)
		        Game:playSound("ui_tab_switch_1")
            end
        end)
    end

    bee.addClick(self:find("ingame_friend_game_side_button", self.SidePanel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("Mask"), function()
        self:hideUI()
    end)

    self.ListBlind = UiListEx:create(self.BlindList)
    self.ListBlind:setWidth(54)
    self.ListBlind:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListBlind:setRefreshFunc(function(data, item)
        self:refreshBlindItem(data, item)
    end)
end

function P:onShow()
    self.transform.localPosition = bee.v3zero
    Net:sendReq("pb.TourRoomDetailREQ", {})

    self.ListBlind:setDatas(GameModel.data:getBlindList())

    bee.setText(self.TextPlayerCount, "" .. GameModel.data:getOnSeatNum() .. "/" .. GameModel.data:getSeatNum())
    bee.setText(self.TextTitle, GameModel.data:getRoomName())
    
    self:removeAllChildren( self.BgItemReward)
    if GameModel.data.room_info.total_reward > 0 then
        self.ItemPrizePool:SetActive(true)
        PropItem:create(self.ItemPrizePool, {id = GPropId.Gold, num = GameModel.data.room_info.total_reward}): bindTips(self.node)
    else
        self.ItemPrizePool:SetActive(false)
    end
    if GameModel.data.room_info.champion_points > 0 then
        PropItem:create(self.ItemPoint, {id = GPropId.ChampionPoints, num = GameModel.data.room_info.champion_points}): bindTips(self.node)
        self.TextPoint:SetActive(false)
        self.ItemPoint:SetActive(true)
    else
        self.TextPoint:SetActive(true)
        self.ItemPoint:SetActive(false)
    end

    self:refreshNextBlind()
    self.Iteam4:SetActive(false)

    self:showView(1)
end

function P:showView(index)
    self._showIndex = index
    for k, v in ipairs(self.Views) do
        v:SetActive(k == index)
    end
end

function P:getBlindText(sb, bb, ante)
    if ante and ante > 0 then
        return _F("{p1}({p2})", _N(sb) .. "/" .. _N(bb), _N(ante))
    else
        return _F("{p1}", _N(sb) .. "/" .. _N(bb))
    end
end

function P:refreshNextBlind()
	local sb = GameModel.data:getSmallBlind()
	local bb = GameModel.data:getBigBlind()
    local ante = GameModel.data:getAnte()
	bee.setText(self.TextBlind, self:getBlindText(sb, bb, ante))
    
    local nextBlindInfo = GameModel.data:getNextBlindInfo()
    if not nextBlindInfo then
        self.TextBlindLimit:SetActive(true)
        self.TextBlindNext:SetActive(false)
        self.TextTime:SetActive(false)
    else
        self.TextBlindLimit:SetActive(false)
        self.TextBlindNext:SetActive(true)
        self.TextTime:SetActive(true)

	    bee.setText(self.TextBlindNext, self:getBlindText(nextBlindInfo.small_blind, nextBlindInfo.big_blind, nextBlindInfo.ante))

        local dt = GameModel.data:getBlindUpTime()
        bee.setText(self.TextTime, TimeHelp:getTimeStrHMS(dt))
        self:once(1, function()
            self:refreshNextBlind()
        end)
    end
end

function P:refreshBlindItem(data, item)
    bee.setText(self:find("TextLevel", item), data.blind_level)
    if data.ante > 0 then
        bee.setText(self:find("TextBlind", item), _N(data.small_blind) .. "/" .. _N(data.big_blind) .. "(" .. _N(data.ante) .. ")")
    else
        bee.setText(self:find("TextBlind", item), _N(data.small_blind) .. "/" .. _N(data.big_blind))
    end
    bee.setText(self:find("TextAnte", item), TimeHelp:getTimeLeftStr(data.duration, true))

    self:find("tournament_sng_details_blind_list_frame_01", item):SetActive(data.blind_level % 2 == 1)
    self:find("tournament_sng_details_blind_list_frame_02", item):SetActive(data.blind_level % 2 == 0)
end

function P:refreshRankList(msg)
    for k, v in ipairs(msg.rank_list) do
        bee.setTextCut(self:find("TextName", self.RankItems[k]), v.brief.name, 210)
        bee.setText(self:find("TextGold", self.RankItems[k]), v.chips)

        self:find("tournament_ingame_rank_frame_04", self.RankItems[k]):SetActive(v.brief.uid == PlayerModel:getUid())
    end
end

function P:evt_TourRoomRankRefreshBRC(msg)
    self:refreshRankList(msg)
end

function P:evt_TourRoomDetailRSP(msg)
    bee.setText(self.TextRank, msg.my_rank)

    self:refreshRankList(msg)

    if msg.sign_item.item_id and msg.sign_item.item_id > 0 then
        self:find("icon_10100001", self.TextByin):SetActive(true)
        bee.setIcon(self:find("icon_10100001", self.TextByin), tpl_props[msg.sign_item.item_id].icon)
        bee.setText(self.TextByin, _N(msg.sign_item.item_num))
    else
        self:find("icon_10100001", self.TextByin):SetActive(false)
        bee.setText(self.TextByin, _T("LAB_SHOP_COMMON_21"))
    end

    if not self.ItemPrizePool.activeSelf and msg.rank_list and #msg.rank_list > 0 then
        for k, v in ipairs(msg.rank_list[1].reward_item_list) do
            local item = nil
            if tpl_props[v.item_id].type == GPropKind.Title then
                item = CU.GameObject.Instantiate(self.ItemTitle, self.BgItemReward.transform, false)
            else
                item = CU.GameObject.Instantiate(self.ItemPrizePool, self.BgItemReward.transform, false)
            end
            item:SetActive(true)
            PropItem:create(item, {id = v.item_id, num = v.item_num}): bindTips(self.node)
        end
    end
    
    if (msg.win_exp and msg.win_exp > 0) or (msg.bond_add and msg.bond_add > 0) then
        self.Iteam4:SetActive(true)
        local BgJoinReward = self:find("BgJoinReward", self.Iteam4)
        local Item1 = self:find("Item1", BgJoinReward)
        Item1:SetActive(false)
        if self._ItemRewards then
            for _, v in ipairs(self._ItemRewards) do
                CU.GameObject.Destroy(v)
            end
        end
        self._ItemRewards = {}
        if msg.win_exp and msg.win_exp > 0 then
            local item = CU.GameObject.Instantiate(Item1, BgJoinReward.transform, false)
            item:SetActive(true)
            table.insert(self._ItemRewards, item)
            PropItem:create(item, {id = GPropId.ExpSNG, num = msg.win_exp, format = {VipModel:getExpTournament()}}): bindTips(self.node)
        end
        if msg.bond_add and msg.bond_add > 0 then
            local item = CU.GameObject.Instantiate(Item1, BgJoinReward.transform, false)
            item:SetActive(true)
            table.insert(self._ItemRewards, item)
            PropItem:create(item, {id = GPropId.BondSNG, num = msg.bond_add, format = {VipModel:getFriendshipTournament()}}): bindTips(self.node)
        end
    else
        self.Iteam4:SetActive(false)
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P