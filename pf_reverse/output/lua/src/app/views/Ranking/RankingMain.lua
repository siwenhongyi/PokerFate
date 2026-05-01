local P = class("RankingMain", UiFullView)

local LikeEffect = {
	[1] = "Prefab/Eff_poker_Ui_Rank_like02",
	[2] = "Prefab/Eff_poker_Ui_Rank_like01",
	[3] = "Prefab/Eff_poker_Ui_Rank_like03",
}

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")
	self.Center = self:find("Center", self.AnimRoot)
	local Left = self:find("Left", self.AnimRoot)
	local LeftBottom = self:find("LeftBottom", self.AnimRoot)
	local LeftTop = self:find("LeftTop", self.AnimRoot)

	self.Loading = self:find("Loading", self.AnimRoot)
	self.playerItemList = {}
	for i = 1, 3 do
		self.playerItemList[i] = self:find("PlayerCont/Rank" .. i, self.Center)
	end
	self.ListButton = self:find("ListButton", self.Center)
	self.RankingBg = self:find("RankingBg", self.Center)
	self.PlayerCont = self:find("PlayerCont", self.Center)
	self.EmptyCont = self:find("EmptyCont", self.Center)
	
	self.SwitchCont = self:find("SwitchCont", self.AnimRoot)
	self.LastWeekButton = self:find("LastWeekButton", self.SwitchCont)
	self.CurWeekButton = self:find("CurWeekButton", self.SwitchCont)

	self.TabButton = self:find("TabButton", Left)
	self.ToggleScrollView = self:find("ToggleScrollView/Viewport/Content", Left)
	self.TabButton:SetActive(false)

	self.ShopButton = self:find("ShopButton", LeftBottom)
	self.InfoButton = self:find("InfoButton", LeftTop)
	self.BackButton = self:find("BackButton", LeftTop)

	bee.addClick(self.BackButton, function()
		bee.logEvent("leaderboard-return")
		self:hideUI()
	end)
	bee.addClick(self.InfoButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("leaderboard-rule")
		UiManager:showUI("RankingRule")
	end)
	bee.addClick(self.ListButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("leaderboard-detail", self._clickId, self._clickSubId)
		UiManager:showUI("RankingList", {id = self._clickId, subId = self._clickSubId})
	end)
	bee.addClick(self.ShopButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("leaderboard-shop")
		ItemModel:jumpView(tpl_constdata.Leaderboard_Shop_Link)
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

function P:preHide()
	P.super.preHide(self)
	AnimationMgr:playAnimator(self.SwitchCont:GetComponent("Animator"), "UI_2_RankingMain_SwitchCont_back")
end

function P:onStart()
	self:setTabButtonList()
	self:refreshTab()
	self:switchRankings()
end

function P:switchRankings()
	self:refreshSwitchCont()
	self.Loading:SetActive(true)
	self.Center:SetActive(false)
	self._waitLoading = true
	RankingModel:requestRankingList(self._clickId, self._clickSubId, 1, true)
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
		self.Loading:SetActive(false)
		self.Center:SetActive(true)
		self:setPlayerCont()
		if self._waitLoading then
			self._waitLoading = false
			self:playAnimator("UI_1_RankingMain_switch", self.AnimRoot)
		end
	end
end

function P:setTabButtonList()
	local rankingList = RankingModel:getRankingTabList()
	if not self._clickId then
		self._clickId = rankingList[1].id
	end
	self._clickSubId = RankingType.CurWeek
	self._tabIdList = {}
	for i, v in ipairs(rankingList) do
		self:initTabButtonItem(v)
	end
end

function P:initTabButtonItem(data)
	local copyTabButton = CU.GameObject.Instantiate(self.TabButton)
	copyTabButton.transform:SetParent(self.ToggleScrollView.transform)
	copyTabButton.transform.localPosition = bee.v3(0, 0, 0)
	copyTabButton.transform.localScale = bee.v3(1, 1, 1)
	copyTabButton:SetActive(true)

	local Animroot = self:find("Animroot", copyTabButton)
	local ToggleIcon = self:find("ToggleIcon", Animroot)
	local NameText = self:find("NameText", Animroot)

	bee.setText(NameText, _T(data.name))
	bee.setIconInAtlas(ToggleIcon, data.icon)

	self._tabIdList[data.id] = {tabBtn = copyTabButton}

	bee.removeAllClick(copyTabButton)
	bee.addClick(copyTabButton, function()
		Game:playSound("ui_tab_switch_1")
		if self._clickId == data.id then
			return
		end

		self._clickId = data.id
		self._clickSubId = RankingType.CurWeek
		-- 刷新数据显示
		self:switchRankings()

		bee.logEvent("leaderboard-tab", self._clickId, self._clickSubId)
		self:refreshTab()
	end)
end

function P:refreshTab()
	for k, v in pairs(self._tabIdList) do
		if k == self._clickId then
			self:find("Animroot", v.tabBtn):GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_into")
		else
			self:find("Animroot", v.tabBtn):GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_idle2")
		end
	end
end

function P:setPlayerCont()
	local list = RankingModel:getRankingList(self._clickId, self._clickSubId)
	if not list or not next(list) then
		self.EmptyCont:SetActive(true)
		self.RankingBg:SetActive(false)
		self.PlayerCont:SetActive(false)
		self.ListButton:SetActive(false)
		return
	end

	self.EmptyCont:SetActive(false)
	self.RankingBg:SetActive(true)
	self.PlayerCont:SetActive(true)
	self.ListButton:SetActive(true)

	for i = 1, 3 do
		self:setPlayerItem(self.playerItemList[i], list[i])
	end
	bee.setIconInAtlas(self.RankingBg, tpl_leaderboard_info[self._clickId].main_bg)
end

function P:setPlayerItem(item, data)
	if not data then
		item:SetActive(false)
		return
	end
	item:SetActive(true)

	local CharacterImg = self:find("Card/CharacterMask/CharacterImg", item)
	local Nameplate = self:find("Nameplate", item)
	local Points = self:find("Points", Nameplate)
	local PointTitle = self:find("PointTitle", Nameplate)
	local PointText = self:find("PointText", Points)
	local PointIcon = self:find("PointIcon/Icon", Points)
	local Information = self:find("Information", Nameplate)
	local AvatarTitle = self:find("AvatarTitle", Information)
	local NameText = self:find("NameText", Information)
	local Avatar = self:find("Avatar", Information)
	local AvatarIcon = self:find("avatar_frame_01_mask/AvatarIcon", Avatar)
	local AvatarFrame = self:find("AvatarFrame", Avatar)
	local LikeCont = self:find("LikeCont", item)
	local LikeButton = self:find("LikeButton", LikeCont)
	local LikeGreyButton = self:find("LikeGreyButton", LikeCont)
	local EffectRoot = self:find("EffectRoot", item)
	local LikeCount = self:find("Number/LikeCount", LikeCont)

	if data.name == "" then
		bee.setText(NameText, _T("LAB_LEADERBOARD_1"))
	else
		bee.setText(NameText, data.name)
	end
	
	bee.setText(PointTitle, _T(tpl_leaderboard_info[self._clickId].name))
	bee.setText(PointText, _N1(data.value))
	bee.setIcon(AvatarIcon, PlayerModel:getAvatarIcon(data.avatar))
	bee.setIconInAtlas(PointIcon, tpl_leaderboard_info[self._clickId].icon_2, true)
	GF.setFrameImage(AvatarFrame, data.frame)
	GF.setTitleImage(AvatarTitle, data.title)
	bee.setText(LikeCount, _N1(data.like))

	local skinCfg = tpl_character_skin[data.skin_id]
	if skinCfg then
		bee.setIcon(CharacterImg, skinCfg.image, true)
		CharacterImg.transform.localPosition = bee.v3(skinCfg.leaderboard_offset[1], skinCfg.leaderboard_offset[2], 0)
		CharacterImg.transform.localScale = bee.v3(skinCfg.leaderboard_offset[3], skinCfg.leaderboard_offset[3], 1)
	end

	if EffectRoot.transform.childCount > 0 then
		for i = 1, EffectRoot.transform.childCount do
			CU.GameObject.Destroy(EffectRoot.transform:GetChild(i - 1).gameObject)
		end
	end

	LikeButton:SetActive(self._clickSubId == RankingType.CurWeek)
	LikeGreyButton:SetActive(self._clickSubId ~= RankingType.CurWeek)

	bee.removeAllClick(LikeButton)
	bee.addClick(LikeButton, function()
		Game:playSound("ui_bubble")
		if not bee.checkCd("LikeRank", 1) then
			local index = math.random(2, 3)
			local eff = AnimationMgr:playUIEffect(LikeEffect[index], EffectRoot.transform)
			return
		end
		local eff = AnimationMgr:playUIEffect(LikeEffect[1], EffectRoot.transform)
		RankingModel:requestLikeRanking(self._clickId, data.rank_id)
	end)

	bee.removeAllClick(LikeGreyButton)
	bee.addClick(LikeGreyButton, function()
		UiManager:showToast(_T("LAB_LEADERBOARD_TIPS_2"))
	end)

	bee.removeAllClick(Avatar)
	bee.addClick(Avatar, function()
		if data.name == "" then
			UiManager:showToast(_T("LAB_LEADERBOARD_TIPS_1"))
			return
		end
		Game:playSound("ui_button_confirm")
		if data.uid == PlayerModel:getUid() then
			UiManager:showUI("InformationMainNew", {from = "Ranking"})
		else
			UiManager:showUI("InformationMainNew", {uid = data.uid, from = "Ranking"})
		end
	end)

	bee.removeAllClick(PointText)
	bee.addClick(PointText, function()
		UiManager:showUI("CommonIconTextTipUD", {icon = tpl_leaderboard_info[self._clickId].icon_2, text = data.value, target = PointText})
	end)

	bee.removeAllClick(LikeCount)
	bee.addClick(LikeCount, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonIconTextTipUD", {icon = "Rankings[rankings_player_like_button_01]", text = data.like, target = LikeCount})
	end)
end

function P:evt_rankingLikeUpdate(param)
	if param.id ~= self._clickId then
		return
	end

	local rankData = RankingModel:getRankingDataById(self._clickId, self._clickSubId, param.rank_id)
	if self.playerItemList[rankData.rank] then
		local item = self.playerItemList[rankData.rank]
		local LikeCount = self:find("LikeCont/Number/LikeCount", item)
		bee.setText(LikeCount, _N1(rankData.like))
	end
end

function P:onClickSwithButton()
	if self._clickSubId == RankingType.CurWeek then
		self._clickSubId = RankingType.LastWeek
	elseif self._clickSubId == RankingType.LastWeek then
		self._clickSubId = RankingType.CurWeek
	end
	self:switchRankings()
end

return P