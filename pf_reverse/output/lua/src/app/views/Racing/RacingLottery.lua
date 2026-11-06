local P = class("RacingLottery", require("app.views.Racing.RacingBase"))

function P:onAwake()
	P.super.onAwake(self)

	self.TitleText = self:find("TitleText", self.Right)
	self.ItemCont = self:find("ItemContent", self.Right)
	self.itemList = {}
	for i = 1, 9 do
		self.itemList[i] = self:find("ItemContent/Item" .. i, self.Right)
	end
	self.ItemCont:SetActive(false)

	self.LotteryButton1 = self:find("LotteryButton1", self.LeftBottom)
	self.LotteryButton2 = self:find("LotteryButton2", self.LeftBottom)
	self.RefreshButton = self:find("RefreshButton", self.LeftBottom)
	self.RefreshButton:SetActive(false)

	self.ClickMask = self:find("ClickMask")
	self.ClickMask:SetActive(false)

	bee.addClick(self.RefreshButton, function()
		self:onClickRefreshButton()
	end)
end

function P:onStart()
	self._playItemAnim = true
	self._refreshButton = true
	ThemeModel:reqThemePool()
	bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100806], true)
end

function P:evt_BackpackClaimResultClose()
	self.RefreshButton:SetActive(ThemeModel:getThemePoolIsCanRefresh(ThemeModel:getThemePoolId()))
end

function P:evt_updateThemePool()
	self.ItemCont:SetActive(true)

	self:setItemCont()
	self:setLotteryButton1()
	self:setLotteryButton2()
	if self._refreshButton then
		self._refreshButton = false
		self:evt_BackpackClaimResultClose()
	end
end

function P:evt_refreshTopInfo()
	P.super.evt_refreshTopInfo(self)
	self:setLotteryButton1()
	self:setLotteryButton2()
end

function P:setItemCont()
	local poolId = ThemeModel:getThemePoolId()
	local list = {}
	for k, v in pairs(get_tpl_subKey(tpl_theme_pool_list, "pool_id", poolId)) do
		local num = ThemeModel:getThemePoolItemNum(v.id)
		table.insert(list, {cfg = v, num = num, remainNum = v.num and v.num - num or 99999})
	end
	table.sort(list, function(a, b)
		local sumA = 100
		local sumB = 100

		-- if a.remainNum <= 0 then
		-- 	sumB = sumB + 10
		-- end
		-- if b.remainNum <= 0 then
		-- 	sumA = sumA + 10
		-- end

		if a.cfg.index < b.cfg.index then
			sumA = sumA + 1
		end
		if a.cfg.index > b.cfg.index then
			sumB = sumB + 1
		end

		return sumA > sumB
	end)

	if self._playItemAnim then
		self._playItemAnim = false
		for i, v in ipairs(list) do
			self:setItem(self.itemList[i], v)
			self.itemList[i]:SetActive(false)
			self:once(0.1 * (i - 1), function()
				self.itemList[i]:SetActive(true)
				AnimationMgr:playAnim(self:find("Ani_root", self.itemList[i]), "UI_1_GalaSeasonShop_item")
			end)
		end
	elseif self._showItemAnimEff then
		self._showItemAnimEff = false
		self.ClickMask:SetActive(true)
		self:once(4.1, function()
			self.ClickMask:SetActive(false)
		end)
		for i, v in ipairs(list) do
			self:once(0.1 * (i - 1), function()
				AnimationMgr:playUIEffect("Prefab/Racing/Eff_poker_Ui_Racing_sx", self.itemList[i].transform, bee.v3(0, 0, 0))
				self:once(0.4, function()
					self:setItem(self.itemList[i], v)
				end)
			end)
		end
	else
		for i, v in ipairs(list) do
			self:setItem(self.itemList[i], v)
		end
	end

	local poolInfo = tpl_theme_pool_info[poolId]
	bee.setText(self.TitleText, _F("LAB_THEME_ACTIVITY7_18", poolInfo.order))
	local remainNum = ThemeModel:getThemePoolRemainNum(poolId)
	self.LotteryButton1:SetActive(remainNum > 0)
	self.LotteryButton2:SetActive(remainNum > 0)
end

function P:setItem(item, data)
	local Ani_root = self:find("Ani_root", item)
	local ItemBg = self:find("ItemBg", Ani_root)
	local PropName = self:find("PropName", Ani_root)
	local PropItemObj = self:find("PropItem", Ani_root)
	local RemainText = self:find("RemainText", Ani_root)
	local PreviewButton = self:find("PreviewButton", Ani_root)
	local Mask = self:find("Mask", Ani_root)

	local propCfg = tpl_props[data.cfg.rewards[1]]
	self:_setPropName(PropName, _T(propCfg.name))

	local p = PropItem:create(PropItemObj, {id = propCfg.id, num = data.cfg.rewards[2]})
	p:bindTips()
	p:hideBg()
	if data.cfg.rewards[2] <= 1 then
		p:hideNum()
	end

	if data.cfg.is_core then
		bee.setIcon(ItemBg, "racing_lottery_bg_product_01", "Racing")
	else
		bee.setIcon(ItemBg, "racing_lottery_bg_product_02", "Racing")
	end
	if data.cfg.num then
		bee.setText(RemainText, _F("LAB_THEME_ACTIVITY7_16", data.remainNum))
	else
		bee.setText(RemainText, _T("LAB_THEME_ACTIVITY8_21"))
	end
	Mask:SetActive(data.cfg.num and data.remainNum <= 0)

	PreviewButton:SetActive(propCfg.preview)
	ItemModel:bindPreviewButton(PreviewButton, propCfg.id)
end

function P:_setPropName(NameItem, NameText)
	local PropNameText = self:find("PropNameText", NameItem)
	bee.setText(PropNameText, NameText)

	local s = NameItem.transform.sizeDelta
	local len = CS.Utils.GetTextWidth(PropNameText:GetComponent("Text"), NameText)
	bee.Tween.killByTarget(PropNameText)

	if len <= s.x then
		PropNameText.transform.localPosition = bee.v3zero
	else
		local offset = (len - s.x) / 2 + 15
		PropNameText.transform.localPosition = bee.v3(offset)
        bee.tween(PropNameText)
        : delay(1)
        : to(5, {position = bee.v3(-offset, 0, 0)})
        : delay(3)
        : to(0, {position = bee.v3(offset, 0, 0)})
        : loop(-1)
        : link()
        : setTarget()
	end
end

function P:setLotteryButton1()
	local poolId = ThemeModel:getThemePoolId()
	if not poolId then
		return
	end

	local Icon = self:find("Icon", self.LotteryButton1)
	local NumText = self:find("NumText", self.LotteryButton1)
	local Text = self:find("Text", self.LotteryButton1)

	local poolCfg = tpl_theme_pool_info[poolId]
	local costId = poolCfg.cost[1]
	local costNum = poolCfg.cost[2]
	local propCfg = tpl_props[costId]
	local ownCount = ItemModel:getItemNumById(costId)
	
	bee.setIconInAtlas(Icon, propCfg.icon)
	bee.setText(Text, "<I>" .. _F("LAB_THEME_ACTIVITY7_17", 1) .. "</I>")
	if ownCount >= costNum then
		bee.setText(NumText, "x" .. _N(costNum))
	else
		bee.setText(NumText, "<color=#FF0000>x" .. _N(costNum) .. "</color>")
	end

	bee.removeAllClick(self.LotteryButton1)
	bee.addClick(self.LotteryButton1, function()
		if ownCount < costNum then
			UiManager:showToast(_T("LAB_COMMON_TIPS_1"))
			UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(costId, true)})
			return
		end
		bee.logEvent("activity-theme-lottery-button", ActivityId.Racing, poolId, 1)
		ThemeModel:reqThemePoolDraw(1)
	end)
end

function P:setLotteryButton2()
	local poolId = ThemeModel:getThemePoolId()
	if not poolId then
		return
	end

	local Icon = self:find("Icon", self.LotteryButton2)
	local NumText = self:find("NumText", self.LotteryButton2)
	local Text = self:find("Text", self.LotteryButton2)

	local poolCfg = tpl_theme_pool_info[poolId]
	local costId = poolCfg.cost[1]
	local costNum = poolCfg.cost[2]
	local propCfg = tpl_props[costId]
	local ownCount = ItemModel:getItemNumById(costId)
	local drawCount = 2
	local maxDrawCount = math.min(ThemeModel:getThemePoolRemainNum(poolId), tpl_constdata.Theme_Lottery_Limit)
	
	bee.setIconInAtlas(Icon, propCfg.icon)
	
	if ownCount >= costNum * drawCount then
		drawCount = math.min(maxDrawCount, math.floor(ownCount / costNum))
		bee.setText(NumText, "x" .. _N(costNum * drawCount))
		bee.setText(Text, "<I>" .. _F("LAB_THEME_ACTIVITY7_17", drawCount) .. "</I>")
	else
		bee.setText(NumText, "<color=#FF0000>x" .. _N(costNum * drawCount) .. "</color>")
		bee.setText(Text, "<I>" .. _F("LAB_THEME_ACTIVITY7_17", drawCount) .. "</I>")
	end

	bee.removeAllClick(self.LotteryButton2)
	bee.addClick(self.LotteryButton2, function()
		if ownCount < costNum * drawCount then
			UiManager:showToast(_T("LAB_COMMON_TIPS_1"))
			UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(costId, true)})
			return
		end
		bee.logEvent("activity-theme-lottery-button", ActivityId.Racing, poolId, drawCount)
		ThemeModel:reqThemePoolDraw(drawCount)
	end)
end

function P:onClickRefreshButton()
	if ThemeModel:getThemePoolRemainNum(ThemeModel:getThemePoolId()) > 0 then
		local params = {}
		params.text = _T("LAB_THEME_ACTIVITY7_20")
		params.onSure = function()
			self._showItemAnimEff = true
			self._refreshButton = true
			bee.logEvent("activity-theme-lottery-new", ActivityId.Racing, ThemeModel:getThemePoolId(), 0)
			ThemeModel:reqThemePoolUnlock()
		end
		UiManager:showTip(params)
	else
		self._showItemAnimEff = true
		self._refreshButton = true
		bee.logEvent("activity-theme-lottery-new", ActivityId.Racing, ThemeModel:getThemePoolId(), 1)
		ThemeModel:reqThemePoolUnlock()
	end
end

function P:hideUI()
    P.super.hideUI(self)
    if self._is_show then
		self:hideTopUI()
	end
end

return P