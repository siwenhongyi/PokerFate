local P = class("RankingList", UiDialog)

local LikeEffect = {
	[1] = "Prefab/Eff_poker_Ui_Rank_like02",
	[2] = "Prefab/Eff_poker_Ui_Rank_like01",
	[3] = "Prefab/Eff_poker_Ui_Rank_like03",
}

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.CloseButton = self:find("CloseButton", Center)
	self.TitleIcon = self:find("Title/TitleIcon", Center)
	self.TitleText = self:find("Title/TitleText", Center)
	self.LastWeekButton = self:find("SwitchCont/LastWeekButton", Center)
	self.CurWeekButton = self:find("SwitchCont/CurWeekButton", Center)
	self.Frame = self:find("TopCont/Frame", Center)
	self.PointText = self:find("TopCont/PointText", Center)
	self.RankingList = self:find("RankingList", Center)
	self.Item1 = self:find("Item1", self.RankingList)
	self.LoadingItem = self:find("LoadingItem", self.RankingList)
	self.Item1:SetActive(false)
	self.LoadingItem:SetActive(false)
	self.Empty = self:find("Empty", Center)
	self.NoData = self:find("NoData", Center)
	self.SelfItem = self:find("SelfItem", Center)
	self.LikeEffectRoot = self:find("LikeEffectRoot", Center)
	self.RightButton = self:find("RightButton", Center)
	self.LeftButton = self:find("LeftButton", Center)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)

	bee.addClick(self.RightButton, function()
		if not bee.checkCd("switch_rankingList", 1) then
			return
		end
		self:onClickRightButton()
	end)
	bee.addClick(self.LeftButton, function()
		if not bee.checkCd("switch_rankingList", 1) then
			return
		end
		self:onClickLeftButton()
	end)

	bee.addClick(self.LastWeekButton, function()
		if self._clickSubId == RankingType.LastWeek then
			return
		end
		self._clickSubId = RankingType.LastWeek
		self:switchRankings()
	end)
	bee.addClick(self.CurWeekButton, function()
		if RankingModel:getIsWaitCloseRanking(self._clickId) then
			-- 待关榜单只有上周数据，没有本周数据
			UiManager:showToast(_T("LAB_LEADERBOARD_TIPS_3"))
			return
		end
		if self._clickSubId == RankingType.CurWeek then
			return
		end
		self._clickSubId = RankingType.CurWeek
		self:switchRankings()
	end)
end

function P:onStart()
	if not self._params then
		return
	end

	self._clickId = self._params.id
	self._clickSubId = self._params.subId

	self._rankingTabList = RankingModel:getRankingTabList()
	self._tabCount = #self._rankingTabList
	for i,v in ipairs(self._rankingTabList) do
		if v.id == self._clickId then
			self._curIndex = i
			break
		end
	end

	self:refreshPanelShow()
	self:initRankingList()
	self:switchRankings()
end

function P:switchRankings()
	self:refreshSwitchCont()
	self._waitInit = true
	self._curCount = 0
	self._maxCount = 0
	self.Empty:SetActive(true)
	self.NoData:SetActive(false)
	self.RankingList:SetActive(false)
	self.SelfItem:SetActive(false)
	RankingModel:requestRankingList(self._clickId, self._clickSubId, 1, true)
end

function P:refreshPanelShow()
	-- 初始化界面显示
	local cfg = tpl_leaderboard_info[self._clickId]
	bee.setIconInAtlas(self.TitleIcon, cfg.icon_1)
	bee.setIconInAtlas(self.Frame, cfg.title_bg)
	bee.setText(self.TitleText, _T(cfg.name))
	bee.setText(self.PointText, _T(cfg.name))
end

function P:refreshSwitchCont()
	if RankingModel:getIsWaitCloseRanking(self._clickId) then
		-- 待关榜单只有上周数据，没有本周数据
		self._clickSubId = RankingType.LastWeek
	end

	self:find("On", self.LastWeekButton):SetActive(self._clickSubId == RankingType.LastWeek)
	self:find("Off", self.LastWeekButton):SetActive(self._clickSubId ~= RankingType.LastWeek)
	self:find("On", self.CurWeekButton):SetActive(self._clickSubId == RankingType.CurWeek)
	self:find("Off", self.CurWeekButton):SetActive(self._clickSubId ~= RankingType.CurWeek)
end

function P:evt_rankingUpdate(param)
	if param.id == self._clickId and param.rankType == self._clickSubId then
		if self._waitInit then
			self._waitInit = false
			self:once(0.12, function()
				self:setRankingListCont()
				self.RankingList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
			end)
		else
			self._rankData = RankingModel:getRankingList(self._clickId, self._clickSubId)
			self._curCount = #self._rankData
			self.rankList:setDatas(self._rankData, false)
			self._loadingNewDatas = false
		end
	end
end

function P:setRankingListCont()
	self._rankData = RankingModel:getRankingList(self._clickId, self._clickSubId)
	if not self._rankData or not next(self._rankData) then
		self.Empty:SetActive(false)
		self.NoData:SetActive(true)
		self.RankingList:SetActive(false)
		self.SelfItem:SetActive(false)
	else
		self.Empty:SetActive(false)
		self.NoData:SetActive(false)
		self.RankingList:SetActive(true)
		self.SelfItem:SetActive(true)

		self._curCount = #self._rankData
		self._maxCount = math.min(RankingModel:getRankingsListSize(self._clickId, self._clickSubId), tpl_leaderboard_info[self._clickId].weekly_num)
		self.rankList:setDatas(self._rankData)

		local selfData = RankingModel:getSelfRankData(self._clickId, self._clickSubId)
		self:setRankItem(self.SelfItem, selfData)
	end
end

function P:initRankingList()
	self.rankList = UiListEx:create(self.RankingList)
	self.rankList:setCreateFunc(function(data)
		if data.__kind == 1 then
			return CU.GameObject.Instantiate(self.LoadingItem)
		end
		return CU.GameObject.Instantiate(self.Item1)
	end)
	self.rankList:setRefreshFunc(function(data, item, isInit, index)
		if data.__kind ~= 1 then
			self:setRankItem(item, data, isInit, index)
		end
	end)
	self.rankList:setTopBottom(15, 0)
	self.rankList:setWidth(175)

	self.rankList:addValueChanged(function()
		if self._loadingNewDatas then
			return
		end
		if self._curCount >= self._maxCount then
			return
		end
		for k,v in pairs(self.rankList:getShows()) do
			if self._curCount == v then
				self:loadNewDatas()
				break
			end
		end
	end)
end

function P:loadNewDatas()
	if self._loadingNewDatas then
		return
	end
	self._loadingNewDatas = true
	self.rankList:append({{__kind = 1}})
	RankingModel:requestRankingList(self._clickId, self._clickSubId, self._curCount / 50 + 1)
end

function P:setRankItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local Rank1 = self:find("Rank1", Ani_root)
	local Rank2 = self:find("Rank2", Ani_root)
	local Rank3 = self:find("Rank3", Ani_root)
	local RankBg = self:find("RankBg", Ani_root)
	local Number = self:find("Number", RankBg)
	local Num1 = self:find("Num1", Number)
	local Num2 = self:find("Num2", Number)
	local Num3 = self:find("Num3", Number)
	local NotAchieved = self:find("NotAchieved", RankBg)
	local PercentCount = self:find("PercentCount", RankBg)
	local NameText = self:find("Information/NameText", Ani_root)
	local Avatar = self:find("Information/Avatar", Ani_root)
	local AvatarImg = self:find("avatar_frame_01_mask/AvatarImg", Avatar)
	local AvatarFrame = self:find("AvatarFrame", Avatar)
	local TitleImg = self:find("Information/TitleImg", Ani_root)
	local TypeIcon = self:find("TypeIcon", Ani_root)
	local CountText = self:find("Points/CountText", Ani_root)
	local PointIcon = self:find("Points/PointIcon", Ani_root)
	local LikeCount = self:find("LikeCount", Ani_root)
	local LikeButtonBg = self:find("LikeButtonBg", Ani_root)
	local LikeButton = self:find("LikeButton", Ani_root)
	local EffectRoot = self:find("EffectRoot", Ani_root)

	if data.name == "" then
		bee.setText(NameText, _T("LAB_LEADERBOARD_1"))
	else
		bee.setText(NameText, data.name)
	end

	bee.setText(CountText, _N1(data.value))
	bee.setIcon(AvatarImg, PlayerModel:getAvatarIcon(data.avatar))
	GF.setFrameImage(AvatarFrame, data.frame)
	GF.setTitleImage(TitleImg, data.title)
	bee.setText(LikeCount, _N1(data.like))
	bee.setIconInAtlas(PointIcon, tpl_leaderboard_info[self._clickId].icon_2, true)
	if data.game_type and tpl_system_icon[data.game_type] then
		bee.setIconInAtlas(TypeIcon, tpl_system_icon[data.game_type].icon)
	else
		bee.setIconInAtlas(TypeIcon, "Rankingslist[rankingslist_player_gameplay_icon_empty]")
	end

	local rank = tonumber(data.rank or 0)
	local rankType = RankingModel:getRankingType(self._clickId, rank)
	Rank1:SetActive(rank == 1)
	Rank2:SetActive(rank == 2)
	Rank3:SetActive(rank == 3)
	RankBg:SetActive(rank > 3 or rankType == -1)
	if rankType == -1 then
		-- 无排名
		Number:SetActive(false)
		NotAchieved:SetActive(true)
		PercentCount:SetActive(false)
		bee.setIconInAtlas(TypeIcon, "Rankingslist[rankingslist_player_gameplay_icon_empty]")
		bee.setText(CountText, "-")
		bee.setText(LikeCount, "-")
	elseif rank >= 4 and rankType == 0 then
		Number:SetActive(true)
		NotAchieved:SetActive(false)
		PercentCount:SetActive(false)

		local h = math.floor(data.rank / 100)
		local t = math.floor((data.rank - h * 100) / 10)
		local u = data.rank - h * 100 - t * 10
		if h > 0 then
			Num1:SetActive(true)
			bee.setIcon(Num1, "rankingslist_rank_number_" .. h, "Rankingslist")
		else
			Num1:SetActive(false)
		end
		if h > 0 or t > 0 then
			Num2:SetActive(true)
			bee.setIcon(Num2, "rankingslist_rank_number_" .. t, "Rankingslist")
		else
			Num2:SetActive(false)
		end
		bee.setIcon(Num3, "rankingslist_rank_number_" .. u, "Rankingslist")
	else
		Number:SetActive(false)
		NotAchieved:SetActive(false)
		PercentCount:SetActive(true)

		bee.setText(PercentCount, rankType .. "%")
	end

	local isShowLike = self._clickSubId == RankingType.CurWeek and rank ~= 0
	LikeButtonBg:SetActive(isShowLike)
	LikeButton:SetActive(isShowLike)

    if isInit and index > 0 then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_RankingList_Item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_RankingList_idle", Ani_root)
    end

   	bee.removeAllClick(LikeButton)
	bee.addClick(LikeButton, function()
		Game:playSound("ui_bubble")
		if self._clickSubId == RankingType.LastWeek then
			UiManager:showToast(_T("LAB_LEADERBOARD_TIPS_2"))
			return
		end
		if not bee.checkCd("LikeRank", 1) then
			local index = math.random(2, 3)
			local eff = AnimationMgr:playUIEffect(LikeEffect[index], self.LikeEffectRoot.transform)
			eff.transform.position = EffectRoot.transform.position
			return
		end
		local eff = AnimationMgr:playUIEffect(LikeEffect[1], self.LikeEffectRoot.transform)
		eff.transform.position = EffectRoot.transform.position
		RankingModel:requestLikeRanking(self._clickId, data.rank_id)
	end)

	bee.removeAllClick(Avatar)
	bee.addClick(Avatar, function()
		if data.name == "" then
			UiManager:showToast(_T("LAB_LEADERBOARD_TIPS_1"))
			return
		end
		Game:playSound("ui_button_confirm")
		if data.uid == 0 or data.uid == PlayerModel:getUid() then
			UiManager:showUI("InformationMain", {from = "Ranking"})
		else
			UiManager:showUI("InformationMain", {uid = data.uid, from = "Ranking"})
		end
	end)

	bee.removeAllClick(CountText)
	bee.addClick(CountText, function()
		if data.rank == 0 then
			return
		end
		Game:playSound("ui_button_confirm")
		local rankData
		if data.uid == PlayerModel:getUid() then
			rankData = RankingModel:getSelfRankData(self._clickId, self._clickSubId)
		else
			rankData = RankingModel:getRankingDataById(self._clickId, self._clickSubId, data.rank_id)
		end
		UiManager:showUI("CommonIconTextTipUD", {icon = tpl_leaderboard_info[self._clickId].icon_2, text = rankData.value, target = CountText})
	end)

	bee.removeAllClick(LikeCount)
	bee.addClick(LikeCount, function()
		if data.rank == 0 then
			return
		end
		Game:playSound("ui_button_confirm")
		local rankData
		if data.uid == PlayerModel:getUid() then
			rankData = RankingModel:getSelfRankData(self._clickId, self._clickSubId)
		else
			rankData = RankingModel:getRankingDataById(self._clickId, self._clickSubId, data.rank_id)
		end
		UiManager:showUI("CommonIconTextTipUD", {icon = "Rankings[rankings_player_like_button_01]", text = rankData.like, target = LikeCount})
	end)
end

function P:evt_rankingLikeUpdate(param)
	if self._clickId ~= param.id then
		return
	end

	for k,v in pairs(self.rankList:getShows()) do
		local data = self.rankList:getData(v)
		if data.rank_id == param.rank_id then
			local LikeCount = self:find("Ani_root/LikeCount", self.rankList:getNode(v))
			local rankData = RankingModel:getRankingDataById(self._clickId, self._clickSubId, param.rank_id)
			bee.setText(LikeCount, _N1(rankData.like))
			break
		end
	end

	local selfData = RankingModel:getSelfRankData(self._clickId, self._clickSubId)
	if selfData.rank_id == param.rank_id then
		local LikeCount = self:find("Ani_root/LikeCount", self.SelfItem)
		bee.setText(LikeCount, selfData.like)
	end
end

function P:onClickRightButton()
	self._curIndex = self._curIndex + 1
	if self._curIndex > self._tabCount then
		self._curIndex = 1
	end

	if self._tabCount > 1 and self._clickSubId == RankingType.CurWeek then
		-- 待关闭榜单不显示本周排行榜，切换时直接跳过
		if RankingModel:getIsWaitCloseRanking(self._rankingTabList[self._curIndex].id) then
			self._curIndex = self._curIndex + 1
			if self._curIndex > self._tabCount then
				self._curIndex = 1
			end
		end
	end
	self._clickId = self._rankingTabList[self._curIndex].id
	self:refreshPanelShow()
	self:switchRankings()
end

function P:onClickLeftButton()
	self._curIndex = self._curIndex - 1
	if self._curIndex < 1 then
		self._curIndex = self._tabCount
	end

	if self._tabCount > 1 and self._clickSubId == RankingType.CurWeek then
		-- 待关闭榜单不显示本周排行榜，切换时直接跳过
		if RankingModel:getIsWaitCloseRanking(self._rankingTabList[self._curIndex].id) then
			self._curIndex = self._curIndex - 1
			if self._curIndex < 1 then
				self._curIndex = self._tabCount
			end
		end
	end
	self._clickId = self._rankingTabList[self._curIndex].id
	self:refreshPanelShow()
	self:switchRankings()
end

