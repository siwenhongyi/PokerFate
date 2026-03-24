local P = class("RankingRule", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.TabList = self:find("TabList", Center)
	self.TabToggle = self:find("TabToggle", self.TabList)
	self.RuleList = self:find("RuleList", Center)
	self.RuleText = self:find("Viewport/Content/RuleText", self.RuleList)
	self.RewardList = self:find("Viewport/Content/RewardList", self.RuleList)
	self.CloseButton = self:find("CloseButton", Center)
	self.TabToggle:SetActive(false)

	self._rewardItems = {}

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	self:initTabList()
	self:refreshTab()
	self:setContShow()
end

function P:initTabList()
	self.tabList = UiListEx:create(self.TabList)
	self.tabList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.TabToggle)
	end)
	self.tabList:setRefreshFunc(function(data, item, isInit, index)
		self:setTabItem(item, data, isInit, index)
	end)
	self.tabList:setWidth(130)

	local ruleList = RankingModel:getRankingRuleList()
	self._clickId = ruleList[1].id
	self.tabList:setDatas(ruleList)
end

function P:setTabItem(item, data)
	local Off = self:find("Off", item)
	local On = self:find("On", item)
	
	bee.setText(self:find("TabText", Off), _T(data.tab_name))
	bee.setText(self:find("TabText", On), _T(data.tab_name))

	bee.removeAllClick(item)
	bee.addClick(item, function()
		self._clickId = data.id
		Game:playSound("ui_tab_switch_1")
		bee.logEvent("leaderboard-rule_tab", data.id)
		self:refreshTab()
		self:setContShow()
	end)
end

function P:refreshTab()
	for _,v in pairs(self.tabList:getShows()) do
		local node = self.tabList:getNode(v)
		local data = self.tabList:getData(v)
		local Off = self:find("Off", node)
		local On = self:find("On", node)
		Off:SetActive(data.id ~= self._clickId)
		On:SetActive(data.id == self._clickId)
	end
end

function P:setContShow()
	local showCont = tpl_leaderboard_rules[self._clickId]
	bee.setText(self.RuleText, _T(showCont.rules_dec))
	self:setRewardListShow(showCont.id, showCont.leaderboard_type)
	self.RuleList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
end

function P:setRewardListShow(ruleId, id)
	if not id then
		self.RewardList:SetActive(false)
		return
	end
	self.RewardList:SetActive(true)

	local RewardTitle1 = self:find("RewardTitle1", self.RewardList)
	local RewardTitle2 = self:find("RewardTitle2", self.RewardList)
	local TitleText = self:find("RewardTitle/TitleText", self.RewardList)
	local RewardItem = self:find("RewardItem", self.RewardList)
	RewardItem:SetActive(false)

	RewardTitle1:SetActive(id == 1)
	RewardTitle2:SetActive(id == 2)

	local cfg = RankingModel:getRuleRewardCfg(ruleId, id)
	for i,v in ipairs(cfg) do
		if not self._rewardItems[i] then
			local copyRewardItem = CU.GameObject.Instantiate(RewardItem)
			copyRewardItem.transform:SetParent(self.RewardList.transform)
			copyRewardItem.transform.localPosition = bee.v3(0, 0, 0)
			copyRewardItem.transform.localScale = bee.v3(1, 1, 1)
			copyRewardItem:SetActive(true)
			table.insert(self._rewardItems, copyRewardItem)
		end

		self._rewardItems[i]:SetActive(true)
		self:setRewardItem(self._rewardItems[i], v, i)
	end

	local rewardCount = #cfg
	local itemCount = #self._rewardItems
	if itemCount > rewardCount then
		for i = rewardCount, itemCount do
			self._rewardItems[i]:SetActive(false)
		end
	end
end

function P:setRewardItem(item, data, index)
	local RankBg = self:find("RankBg", item)
	local RankText = self:find("RankText", item)
	local Props = self:find("Props", item)
	local PropItemObj = self:find("Props/PropItem", item)

	local i = index % 2
	RankBg:SetActive(i ~= 0)

	if data.ranking_type == 0 then
		if data.ranking[1] == data.ranking[2] then
			bee.setText(RankText, data.ranking[1])
		else
			bee.setText(RankText, _F("LAB_LEADERBOARD_5", data.ranking[1], data.ranking[2]))
		end
	else
		bee.setText(RankText, _F("LAB_LEADERBOARD_14", data.ranking_type))
	end

	local rewardList = ShopModel:getRewardsList(data.rewards)
	local childCount = Props.transform.childCount
	for i, v in ipairs(rewardList) do
		local prop
		if i <= childCount then
			prop = Props.transform:GetChild(i - 1).gameObject
		else
			prop = CU.GameObject.Instantiate(PropItemObj)
			prop.transform:SetParent(Props.transform)
			prop.transform.localPosition = bee.v3(0, 0, 0)
			prop.transform.localScale = PropItemObj.transform.localScale
		end
		prop:SetActive(true)
		PropItem:create(prop, v)
	end

	local rewardCount = #rewardList
	if childCount > rewardCount then
		for i = rewardCount + 1, childCount do
			Props.transform:GetChild(i - 1).gameObject:SetActive(false)
		end
	end
end

