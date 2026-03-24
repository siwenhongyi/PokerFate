local P = class("Shop", UiFullView)

local SubView = {
	[1] = {		-- 精选推荐
		[101] = {view = "views/Shop/ShopFirstRecharge"},	-- 首充
		[102] = {view = "views/Shop/ShopMonthlyCard"},	-- 月卡
		[103] = {view = "views/Shop/ShopNewComerExclusive"} -- 新人专属
	},
	[2] = {view = "views/Shop/ShopSkin"},		-- 皮肤商城
	[3] = {view = "views/Shop/ShopPackage"},	-- 特惠商城
	[4] = {view = "views/Shop/ShopExchange"},	-- 兑换商城
	[5] = {view = "views/Shop/ShopTopUp"},	-- 充值
	[6] = {		-- 装饰商店
		[601] = {view = "views/Shop/ShopDecorateTheme"},	-- 主题商店
		[602] = {view = "views/Shop/ShopDecorate"},	-- 场景商店
		[603] = {view = "views/Shop/ShopDecorate"},	-- 对战商店
		[604] = {view = "views/Shop/ShopDecorateMusic"},	-- 音乐商店
		[605] = {view = "views/Shop/ShopDecorateMusic"},	-- 特效商店
	}
}

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	self.Bg = self:find("bg_fullscreen_01", self.AnimRoot)

	local Center = self:find("Center", self.AnimRoot)
	local RightTop = self:find("RightTop", self.AnimRoot)
	local Left = self:find("Left", self.AnimRoot)
	local LeftTop = self:find("LeftTop", self.AnimRoot)

	bee.addClick(self:find("BackButton", LeftTop), function()
		self:hideUI()
	end)

	bee.addClick(self:find("VIPButton", Left), function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-vip")
		UiManager:showUI("VIP")
	end)

	self.TopTab = self:find("TopTab", Center)
	self.TopTabScrollView = self:find("TopTabScrollView", self.TopTab)
	self.TopTabToggle = self:find("TopTabToggle", self.TopTab)
	self.CenterCont = self:find("CenterCont", Center)
	self.TopTabToggle:SetActive(false)

	self.CurrencyColumn = self:find("CurrencyColumn", RightTop)
	self.Currency = self:find("Currency", RightTop)
	self.Currency:SetActive(false)

	self.ToggleScrollView = self:find("ToggleScrollView", Left)
	self.TabToggle = self:find("TabToggle", Left)
	self.TabToggle:SetActive(false)

	self._currencyObjList = {}

	RedManager:bind(self:find("VIPButton/common_reddot_01", Left), RedTag.VipClaimNum)

	self._firstOpen = true
end

function P:onStart()
	if self._params and self._params.jump then
		self._selectSideTab = self._params.jump.sub_page[1]
		self._selectTopTab = self._params.jump.sub_page[2] or self._selectSideTab
		self._jumpTo = self._params.jumpId
	else
		Game:playSound("ui_shop_open")
	end

	self:initToggleList()
	self:initTopTabList()

	self:refreshTopTab()
	
	ShopModel:initInfo()
end

function P:evt_refreshTopInfo()
	self:refreshCurrency()
end

function P:evt_ItemChangeRSP()
	self:refreshCurrency()

	-- 装饰商店
	if self._selectSideTab == 6 then
		if self._curSubViewCls then
			self._curSubViewCls:refreshUI()
		end
	end
end

function P:evt_SkinUnlockRSP()
	if self._curSubViewCls then
		self._curSubViewCls:refreshUI()
	end
end

function P:evt_updateShopLimit()
	if self._curSubViewCls then
		self._curSubViewCls:refreshUI()
	end
end

function P:initToggleList()
	self.tabtoggleList = UiListEx:create(self.ToggleScrollView)
	self.tabtoggleList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.TabToggle)
	end)
	self.tabtoggleList:setRefreshFunc(function(data, item)
		self:setTabToggle(item, data)
	end)
	self.tabtoggleList:setWidth(120)

	local tabs = ShopModel:getShopSideTabs()
	if not self._selectSideTab then
		self._selectSideTab = tabs[1].id
	end
	self.tabtoggleList:setDatas(tabs)
	self:refreshTabToggle()
end

function P:refreshTabToggle()
	for k, v in pairs(self.tabtoggleList:getDatas()) do
		if v.node then
			if v.data.id == self._selectSideTab then
				self:playToggleInto(v.node)
			else
				self:playToggleIdle2(v.node)
			end
		end
	end
end

function P:initTopTabList()
	self.topTabList = UiListEx:create(self.TopTabScrollView)
	self.topTabList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.TopTabToggle)
	end)
	self.topTabList:setRefreshFunc(function(data, item)
		self:setTopTab(item, data)
	end)
	self.topTabList:setWidth(275)
end

function P:setTabToggle(item, data)
	local ToggleIcon = self:find("ToggleIcon", item)
	local NameText = self:find("NameText", item)

	bee.setIconInAtlas(ToggleIcon, data.page_icon, true)
	bee.setText(NameText, _T(data.name))

	bee.removeAllClick(item)
	bee.addClick(item, function()
		if self._selectSideTab == data.id then
			return
		end
		Game:playSound("ui_tab_switch_1")
		self._selectSideTab = data.id
		self._selectTopTab = nil
		self:refreshTopTab()
		self:refreshTabToggle()
	end)

	local RedPoint = self:find("RedPoint", item)
	RedManager:unbind(RedPoint)
	if data.id == 1 then
		RedManager:bind(RedPoint, RedTag.Recommend)
	elseif data.id == 5 then
		RedManager:bind(RedPoint, RedTag.Recharge)
	else
		RedPoint:SetActive(false)
	end

	local NewTag = self:find("NewTag", item)
	RedManager:unbind(NewTag)
	if data.id == 6 then
		RedManager:bind(NewTag, RedTag.DecorateNew)
	elseif data.id == 2 then
		RedManager:bind(NewTag, RedTag.SkinNew)
	else
		NewTag:SetActive(false)
	end
end

function P:setTopTab(item, data)
	local NameTextOn = self:find("NameTextOn", item)
	local NameTextOff = self:find("NameTextOff", item)
	
	bee.setToggleGroup(item, self.TopTabScrollView)

	if self._selectTopTab == data.id then
		bee.setCheck(item)
		NameTextOn:SetActive(true)
		NameTextOff:SetActive(false)
	else
		bee.setUncheck(item)
		NameTextOn:SetActive(false)
		NameTextOff:SetActive(true)
	end

	bee.setText(NameTextOn, _T(data.name))
	bee.setText(NameTextOff, _T(data.name))

	local RedPoint = self:find("RedPoint", item)
	RedManager:unbind(RedPoint)
	if data.id == 101 then
		RedManager:bind(RedPoint, RedTag.FirstRecharge)
	elseif data.id == 503 then
		RedManager:bind(RedPoint, RedTag.DailyFree)
	end

	local NewTag = self:find("NewTag", item)
	RedManager:unbind(NewTag)
	if self._selectSideTab == 6 then
		RedManager:bind(NewTag, RedTag.DecorateNew, data.shop_type)
	end

	bee.removeValueChanged(item)
	bee.addValueChanged(item, function(isOn)
		if isOn then
			if self._selectTopTab == data.id then
				return
			end
			Game:playSound("ui_tab_switch_2")
			self._selectTopTab = data.id
			self:refreshCenter()
			self:refreshCurrency()
			NameTextOn:SetActive(true)
			NameTextOff:SetActive(false)
		else
			NameTextOn:SetActive(false)
			NameTextOff:SetActive(true)
		end
	end)
end

function P:refreshTopTab()
	local topTabs = ShopModel:getShopSubTabs(self._selectSideTab)
	if topTabs then
		self.TopTab:SetActive(true)
		if not self._selectTopTab then
			self._selectTopTab = topTabs[1].id
		end

		self.topTabList:clear()
		self.topTabList:setDatas(topTabs)
	else
		self.TopTab:SetActive(false)
		self._selectTopTab = self._selectSideTab
	end

	self:refreshCenter()
	self:refreshCurrency()
end

function P:refreshCenter()
	local viewInfo = SubView[self._selectSideTab].view and SubView[self._selectSideTab] or SubView[self._selectSideTab][self._selectTopTab]
	if not viewInfo then
		return
	end

	bee.logEvent("shop-view", tpl_shop_page[self._selectTopTab].shop_type)

	if self._curSubView then
		CU.GameObject.Destroy(self._curSubView)
		self._curSubView = nil
	end

	self._curSubView = bee.createObj(viewInfo.view)
	self._curSubView.transform:SetParent(self.CenterCont.transform)
	local rectTrans = self._curSubView.transform:GetComponent("RectTransform")
	rectTrans.offsetMin = bee.v2(0, 0)
	rectTrans.offsetMax = bee.v2(0, 0)
	self._curSubView.transform.localScale = bee.v3(1, 1, 1)
	
	self._curSubViewCls = ObjectPool:getCls(self._curSubView)
	self._curSubViewCls:setParams({shop_type = tpl_shop_page[self._selectTopTab].shop_type})
	if self._jumpTo then
		if self._curSubViewCls.selectItem then
			self._curSubViewCls:selectItem(self._jumpTo)
		end
		self._jumpTo = nil
	end

	local pageInfo = tpl_shop_page[self._selectTopTab]
	if pageInfo.shop_bg then
		bee.setIcon(self.Bg, pageInfo.shop_bg)
	end
	if pageInfo.unselected_color then
		for k,v in pairs(self.topTabList:getDatas()) do
			bee.setColor(self:find("NameTextOff", v.node), CU.Color(pageInfo.unselected_color[1] / 255, pageInfo.unselected_color[2] / 255, pageInfo.unselected_color[3] / 255), "Text")
		end
	end

	if self._firstOpen and self._selectTopTab == 102 then
		self._curSubView:SetActive(false)
		self:once(0.2, function()
			self._curSubView:SetActive(true)
		end)
	end
	self._firstOpen = false
end

function P:refreshCurrency()
	local currencyList = ShopModel:getCurrencyBar(self._selectTopTab)
	local count = math.max(#currencyList, #self._currencyObjList)
	
	for i = 1, count do
		self:setCurrencyItem(self._currencyObjList[i], currencyList[i])
	end
end

function P:setCurrencyItem(currency, data)
	if not data then
		if currency then
			currency.obj:SetActive(false)
		end
		return
	end

	local item = currency and currency.obj
	if not item then
		item = CU.GameObject.Instantiate(self.Currency)
		item.transform:SetParent(self.CurrencyColumn.transform)
		item.transform.localPosition = bee.v3(0, 0, 0)
		item.transform.localScale = bee.v3(1, 1, 1)
		table.insert(self._currencyObjList, {obj = item})
	end

	item:SetActive(true)

	local ItemIcon = self:find("ItemIcon", item)
	local CountText = self:find("CountText", item)
	local AddButton = self:find("AddButton", item)
	
	local propCfg = tpl_props[data.id]
	bee.setIconInAtlas(ItemIcon, propCfg.icon)
	bee.setTextGold(CountText, _N(ItemModel:getItemNumById(data.id)))
	AddButton:SetActive(data.isAdd ~= 0)

	bee.removeAllClick(item)
	bee.addClick(item, function()
		if data.isAdd == 0 then
			return
		end
		bee.logEvent("shop-add", tpl_shop_page[self._selectTopTab].shop_type, data.id)
		ItemModel:jumpView(data.isAdd)
	end)
	bee.addClick(self:find("ItemIcon", item), function()
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(data.id, true), target = self:find("ItemIcon", item)})
	end, true)
end

