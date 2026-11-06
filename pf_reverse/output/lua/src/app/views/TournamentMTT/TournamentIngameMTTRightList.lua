local P = class("TournamentIngameMTTRightList", UiDialog)

function P:onAwake()
    self.Right = self:find("AnimRoot/Right")
    self.SidePanel = self:find("SidePanel", self.Right)

    local Tabs = self:find("Tabs", self.SidePanel)

    self.Tabs = {
        self:find("DetailsButton", Tabs),
        self:find("RankButton", Tabs),
        self:find("BlindsButton", Tabs),
        self:find("AwardsButton", Tabs),
        self:find("SpectateButton", Tabs),
    }

    self.Views = {
        self:find("Details", self.SidePanel),
        self:find("Ranking", self.SidePanel),
        self:find("Blinds", self.SidePanel),
        self:find("Awards", self.SidePanel),
        self:find("Tables", self.SidePanel),
    }

    local Time = self:find("Time", self.Views[1])
    self.TextBlind = self:find("TextBlind", Time)
    self.TextTime = self:find("TextTime", Time)
    self.TextBlindNext = self:find("TextBlindNext", Time)
    self.TextCurLevel = self:find("TextCurLevel", Time)
    self.TextDelaySign = self:find("TextDelaySign", Time)
    self.TextBlindLimit = self:find("TextBlindLimit", Time)
    self.TextExpired01 = self:find("TextExpired01", Time)
    self.TextExpired02 = self:find("TextExpired02", Time)
    self.TextRest = self:find("TextRest", Time)

    local DetailContent = self:find("DetailList/Viewport/Content", self.Views[1])
    self.DetailItemBase = self:find("ItemBase", DetailContent)
    self.DetailItemByin = self:find("ItemByin", DetailContent)
    self.DetailItemChips = self:find("ItemChips", DetailContent)
    self.DetailItemPrize = self:find("ItemPrize", DetailContent)
    self.DetailItemPoint = self:find("ItemPoint", DetailContent)
    self.DetailItemExp = self:find("ItemExp", DetailContent)

    self.RankEmpty = self:find("Empty", self.Views[2])
    self.RankList = self:find("RankList", self.Views[2])
    self.RankItems = {
        self:find("Item1", self.RankList),
        self:find("Item2", self.RankList),
        self:find("Item3", self.RankList),
        self:find("Item4", self.RankList),
    }
    for _, v in ipairs(self.RankItems) do
        v:SetActive(false)
    end

    self.BlindList = self:find("BlindList", self.Views[3])
    self.Item1 = self:find("Item1", self.BlindList)
    self.Item1:SetActive(false)

    self.AwardsList = self:find("AwardsList", self.Views[4])
    self.AwardsItems = {
        self:find("Item1", self.AwardsList),
        self:find("Item2", self.AwardsList),
        self:find("Item3", self.AwardsList),
        self:find("Item4", self.AwardsList),
    }
    for _, v in ipairs(self.AwardsItems) do
        v:SetActive(false)
    end
    self.ItemAwards = self:find("Item", self.AwardsList)
    self.ItemAwards:SetActive(false)

    -- 牌桌列表
    self.TableList = self:find("TableList", self.Views[5])
    self.TableItem = self:find("Item1", self.TableList)
    self.TableItem:SetActive(false)

    for k, v in ipairs(self.Tabs) do
        bee.onCheck(v, function(isOn)
            if isOn then
                self:showView(k)
		        Game:playSound("ui_tab_switch_1")
                bee.logEvent("tournament-mtt-detail-type", GameModel.data.room_info.tour_id, k)
            end
        end)
    end

    bee.addClick(self:find("ingame_friend_game_side_button", self.SidePanel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("Mask"), function()
        self:hideUI()
    end)
    bee.addClick(self:find("InfoButton", self.Views[4]), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("TournamentMTTpayout", {data = {tour_id = GameModel.data.room_info.tour_id}})
    end)
    bee.addClick(self:find("InfoButton", self.Views[3]), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("TournamentMTTBlindTip", {data = GameModel.data.room_info, target = self:find("InfoButton", self.Views[3])})
    end)

    self.ListBlind = UiListEx:create(self.BlindList)
    self.ListBlind:setWidth(54)
    self.ListBlind:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListBlind:setRefreshFunc(function(data, item)
        self:refreshBlindItem(data, item)
    end)

    self.ListRank = UiListEx:create(self.RankList)
    self.ListRank:setWidth(100)
    self.ListRank:setCreateFunc(function(data)
        if data.rank <= 3 then
            return CU.GameObject.Instantiate(self.RankItems[data.rank])
        end
        return CU.GameObject.Instantiate(self.RankItems[4])
    end)
    self.ListRank:setRefreshFunc(function(data, item)
        self:refreshRankItem(data, item)
    end)

    self.ListAwards = UiListEx:create(self.AwardsList)
    self.ListAwards:setWidth(100)
    self.ListAwards:setCreateFunc(function(data)
        if data.rank <= 3 then
            return CU.GameObject.Instantiate(self.AwardsItems[data.rank])
        end
        return CU.GameObject.Instantiate(self.AwardsItems[4])
    end)
    self.ListAwards:setRefreshFunc(function(data, item)
        self:refreshAwardsItem(data, item)
    end)

    self.ListTables = UiListEx:create(self.TableList)
    self.ListTables:setWidth(90)
    self.ListTables:setTopBottom(0, 180)
    self.ListTables:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.TableItem)
    end)
    self.ListTables:setRefreshFunc(function(data, item)
        self:refreshTableItem(data, item)
    end)
end

function P:onShow()
    self.transform.localPosition = bee.v3zero
    self.DetailItemExp:SetActive(false)
    Net:sendReq("pb.MttRoomDetailREQ", {})

    self.ListBlind:setDatas(GameModel.data:getBlindList())

    -- bee.setText(self.TextPlayerCount, "" .. GameModel.data:getOnSeatNum() .. "/" .. GameModel.data:getSeatNum())
    bee.setText(self.TextPlayerCount, "")
    if GameModel.data.room_info.break_interval > 0 and GameModel.data.room_info.break_duration > 0 then
        self.TextExpired01:SetActive(true)
        self.TextExpired02:SetActive(false)
        self.TextRest:SetActive(true)

        bee.setText(self.TextRest, _F("LAB_TOURNAMENT_MTT_INFO35", GameModel.data.room_info.break_interval / 60, GameModel.data.room_info.break_duration / 60))
    else
        self.TextExpired01:SetActive(false)
        self.TextExpired02:SetActive(true)
        self.TextRest:SetActive(false)
    end
    
    self:refreshGameTime()
    self:refreshNextBlind()

    -- self:showView(1)
    bee.setCheck(self.Tabs[self._showIndex or 1], true, true)

    self:schedule(1, function()
        self:refreshGameTime()
    end)

    local InfoButton = self:find("InfoButton", self.Views[4])
    if InfoButton then
        InfoButton:SetActive(GameModel.data.room_info.gtd and GameModel.data.room_info.gtd > 0 or GameModel.data.room_info.byin_chips > 0)
    end
end

function P:showView(index)
    self._showIndex = index
    for k, v in ipairs(self.Views) do
        v:SetActive(k == index)
    end
    if 2 == index then
        Net:sendReq("pb.MttRankREQ", {tour_id = GameModel.data.room_info.tour_id}, function(resp)
            if not bee.isNull(self.node) and resp and resp.rank_list then
                for _, v in ipairs(resp.rank_list) do
                    v.__kind = v.rank <= 3 and v.rank or 4
                end
                self.ListRank:setDatas(resp.rank_list)
                self.RankEmpty:SetActive(#resp.rank_list == 0)
            end
        end)
    elseif 3 == index then
    elseif 4 == index then
        Net:sendReq("pb.MttRankRewardREQ", {tour_id = GameModel.data.room_info.tour_id}, function(resp)
            if not bee.isNull(self.node) and resp and resp.rank_reward_list then
                for _, v in ipairs(resp.rank_reward_list) do
                    v.__kind = v.rank <= 3 and v.rank or 4
                end
                self.ListAwards:setDatas(resp.rank_reward_list)
            end
        end)
    end
end

function P:getBlindText(sb, bb, ante)
    if ante and ante > 0 then
        return _F("{p1} ({p2})", _N(sb) .. "/" .. _N(bb), _N(ante))
    else
        return _F("{p1}", _N(sb) .. "/" .. _N(bb))
    end
end

function P:refreshGameTime()
    if self._detailData then
        local dt = self._detailData.game_time
        if GameModel.data:getRestLeftTime() <= 0 and GameModel.data:getAddOnBuyinRemainTime() <= 0 and GameModel.data:isMttStart() then
            local ct = os.time()
            if ct > self._detailData.game_time_st then
                self._detailData.game_time = self._detailData.game_time + (ct - self._detailData.game_time_st)
                self._detailData.game_time_st = ct
            end
        end
        local dt = self._detailData.game_time
        local s = _F("LAB_TOURNAMENT_MTT_INFO34", TimeHelp:getTimeStr(dt))
        bee.setText(self.TextExpired01, s)
        bee.setText(self.TextExpired02, s)
    else
        bee.setText(self.TextExpired01, "")
        bee.setText(self.TextExpired02, "")
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

    if GameModel.data.room_info.late_reg_level > 0 then
        self.TextCurLevel:SetActive(true)
        self.TextDelaySign:SetActive(true)
        bee.setText(self.TextCurLevel, _T("LAB_TOURNAMENT_11") .. "<color=#CD9110>" .. GameModel.data:getBlindLevel() .. "</color>")
        bee.setText(self.TextDelaySign, _T("LAB_TOURNAMENT_MTT_INFO30") .. "<color=#CD9110>" .. (GameModel.data.room_info.late_reg_level) .. "</color>")
    else
        self.TextCurLevel:SetActive(false)
        self.TextDelaySign:SetActive(false)
    end
end

function P:refreshBlindItem(data, item)
    bee.setText(self:find("TextLevel", item), data.blind_level)
    bee.setText(self:find("TextBlind", item), _N(data.small_blind) .. "/" .. _N(data.big_blind))
    bee.setText(self:find("TextAnte", item), _N(data.ante))

    self:find("tournament_sng_details_blind_list_frame_01", item):SetActive(data.blind_level % 2 == 1)
    self:find("tournament_sng_details_blind_list_frame_02", item):SetActive(data.blind_level % 2 == 0)
    self:find("tournament_mttlist_img_xuanzhong", item):SetActive(GameModel.data:getBlindLevel() == data.blind_level)

    self:find("icon/tournament_ingame_blind_icon_rebuy", item):SetActive(GameModel.data.room_info.can_reby and data.blind_level <= GameModel.data.room_info.late_reg_level)
    self:find("icon/tournament_ingame_blind_icon_addon", item):SetActive(GameModel.data.room_info.can_addon and data.blind_level == GameModel.data.room_info.late_reg_level)
end

function P:refreshRankItem(data, item)
    bee.setTextCut(self:find("TextName", item), GF.getOtherName(data.brief, data.seat_index + 1), 230)
    bee.setText(self:find("TextGold", item), GameModel.data:getBetChipsStr(data.chips))
    if data.rank >= 4 then
        local BgNums = self:find("BgNums", item)
        BgNums.transform.localScale = data.rank >= 1000 and bee.v3(0.6, 0.6, 0.6) or bee.v3one
        
        local rank = data.rank
        for i = 4, 1, -1 do
            if rank > 0 then
                self:find("Num_" .. i, BgNums):SetActive(true)
                local num = rank % 10
                bee.setIcon(self:find("Num_" .. i, BgNums), "Rankingslist[rankingslist_rank_number_" .. num .. "]")
                rank = math.floor(rank / 10)
            else
                self:find("Num_" .. i, BgNums):SetActive(false)
            end
        end
    end

    self:find("tournament_mttlist_img_xuanzhong", item):SetActive(data.brief.uid == PlayerModel:getUid())
end

function P:refreshAwardsItem(data, item)
    if data.rank >= 4 then
        local BgNums = self:find("BgNums", item)
        BgNums.transform.localScale = data.rank >= 1000 and bee.v3(0.6, 0.6, 0.6) or bee.v3one

        local rank = data.rank
        for i = 4, 1, -1 do
            if rank > 0 then
                self:find("Num_" .. i, BgNums):SetActive(true)
                local num = rank % 10
                bee.setIcon(self:find("Num_" .. i, BgNums), "Rankingslist[rankingslist_rank_number_" .. num .. "]")
                rank = math.floor(rank / 10)
            else
                self:find("Num_" .. i, BgNums):SetActive(false)
            end
        end
    end

    local BgItems = self:find("BgItems", item)
    local Content = self:find("ViewItems/Viewport/Content", item)
    self:removeAllChildren(BgItems)
    self:removeAllChildren(Content)
    if #data.reward_item_list >= 3 then
        BgItems = Content
        self:find("ViewItems", item):SetActive(true)
    else
        self:find("ViewItems", item):SetActive(false)
    end
    if data.reward_item_list then
        GF.addItemsToParent(BgItems, self.ItemAwards, data.reward_item_list, BgItems == Content and data or nil)
    end
end

function P:refreshTableItem(data, item)
    bee.setText(self:find("TextIndex", item), "No." .. data.index)  -- 直接使用英文
    bee.setText(self:find("People/TextPlayer", item), data.player_num)
    bee.setText(self:find("Chip/TextChip", item), GameModel.data:getBetChipsStr(data.max_chips) .. "/" .. GameModel.data:getBetChipsStr(data.min_chips))
    self:find("tournament_mttlist_img_xuanzhong", item):SetActive(GameModel.data:getTid() == data.tid)
    local SpectateButton = self:find("SpectateButton", item)
    if GameModel.data:isInObserve() then
        SpectateButton:SetActive(GameModel.data:getTid() ~= data.tid)
        self:find("ingame_icon_spectate", item):SetActive(GameModel.data:getTid() == data.tid)
        bee.addClick(SpectateButton, function()
            Game:playSound("ui_button_confirm")
            GameModel.stopGameMsg = true
            UiManager:showUI("LoadingLayer", {cb = function()
                bee.logEvent("tournament-mtt-view", GameModel.data.room_info.tour_id, data.tid)
                Net:sendReq("pb.ChangeObserveViewREQ", {tid = data.tid, seatid_being_observed = -1})
                UiManager:hideUI("LoadingLayer")
            end})
        end, true)
    else
        SpectateButton:SetActive(false)
        self:find("ingame_icon_spectate", item):SetActive(false)
    end
end

function P:evt_MttRoomDetailRSP(msg)
    bee.setText(self:find("TextRank", self.DetailItemBase), msg.my_rank > 0 and msg.my_rank or "-" )
    bee.setText(self:find("TextPlayerCount", self.DetailItemBase), "" .. msg.left_players .. "/" .. msg.cur_sign_num)

    local TextByin = self:find("TextByin", self.DetailItemBase)
    TournamentModel:setByinTextByMttData(GameModel.data.room_info, TextByin, self:find("icon_10100001", TextByin))

    bee.setText(self:find("Text", self.DetailItemPrize), msg.total_reward > 0 and _N(msg.total_reward) or "-")

    bee.setText(self:find("TextAveChips", self.DetailItemChips), msg.avg_chips > 0 and GameModel.data:getBetChipsStr(msg.avg_chips) or "-")
    bee.setText(self:find("TextMaxChips", self.DetailItemChips), msg.max_chips > 0 and GameModel.data:getBetChipsStr(msg.max_chips) or "-")
    bee.setText(self:find("TextMinChips", self.DetailItemChips), msg.min_chips > 0 and GameModel.data:getBetChipsStr(msg.min_chips) or "-")

    -- self.DetailItemPoint:SetActive(msg.champion_points > 0)
    if msg.champion_points > 0 then
        bee.setText(self:find("Text", self.DetailItemPoint), _N(msg.champion_points))
    else
        bee.setText(self:find("Text", self.DetailItemPoint), "-")
    end

    bee.setText(self:find("TextBy", self.DetailItemByin), msg.sign_cnt > 0 and msg.sign_cnt or "-")
    bee.setText(self:find("TextReby", self.DetailItemByin), msg.reby_cnt > 0 and msg.reby_cnt or "-")
    bee.setText(self:find("TextAdd", self.DetailItemByin), msg.addon_cnt > 0 and msg.addon_cnt or "-")
        
    msg.game_time_st = os.time()
    self._detailData = msg
    self:refreshGameTime()

    for k, v in ipairs(msg.table_list) do
        v.index = k
    end
    bee.setText(self:find("Table/TextTableNum", self.Views[5]), _F("LAB_TOURNAMENT_MTT_INFO58", #msg.table_list))
    self.ListTables:setDatas(msg.table_list)

    if (msg.win_exp and msg.win_exp > 0) or (msg.bond_add and msg.bond_add > 0) then
        self.DetailItemExp:SetActive(true)
        local BgJoinReward = self:find("BgJoinReward", self.DetailItemExp)
        local Item1 = self:find("Item1", self.DetailItemExp)
        Item1:SetActive(false)
        self:removeAllChildren(BgJoinReward)
        
        local items = {{id = GPropId.ExpSNG, num = msg.win_exp, format = {VipModel:getExpTournament()}}, {id = GPropId.BondSNG, num = msg.bond_add, format = {VipModel:getFriendshipTournament()}}}
        GF.addItemsToParent(BgJoinReward, Item1, items)
    else
        self.DetailItemExp:SetActive(false)
    end
end

function P:evt_MttPlayerNumChangeBRC(msg)
    Net:sendReq("pb.MttRoomDetailREQ", {})
end

function P:evt_WinnerRSP()
    Net:sendReq("pb.MttRoomDetailREQ", {})
end

function P:evt_ChangeTableRSP(msg)
    self.ListTables:refreshShowingUi()
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P