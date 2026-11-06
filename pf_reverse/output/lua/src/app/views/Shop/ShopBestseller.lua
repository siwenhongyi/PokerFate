local P = class("ShopBestseller", UiFullView)

local SubView = {
	[1] = {view = "views/Shop/ShopMonthlyCard", pos = {0, 0}},	-- 月卡
	[2] = {view = "views/Shop/ShopBestsellerColorCrystal", pos = {153, 0}},	-- 轮盘彩晶
	[3] = {
		[10006] = {view = "views/Sayaka/SayakaPackageBase", pos = {0, 0}},	-- 泳装活动礼包
	},
	[4] = {view = "views/Shop/ShopFirstRecharge", pos = {30.58, 62.8}},	-- 首充
	[5] = {view = "views/Shop/ShopNewComerExclusive", pos = {62.5, 56.5}}, -- 新人专属
	[10001] = {view = "views/Shop/ShopSayakaExclusive", pos = {0, 0}},	-- 冈田纱佳礼包
	[20001] = {view = "views/Matsuri/MatsuriPackageBase", pos = {0, 0}},	-- 夏日祭活动礼包
	[20002] = {view = "views/Racing/RacingPackageBase", pos = {165, 0}},	-- 赛车祭活动礼包
	[20003] = {view = "views/Fantasy/FantasyPackageBase", pos = {160, -82}},	-- 日幻活动礼包
	[30001] = {view = "views/Shop/ShopBestsellerSkin", pos = {0, 0}},		-- 服饰复刻
}

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")
	self.Center = self:find("Center", self.AnimRoot)
	self.Left = self:find("Left", self.AnimRoot)

	self.Bg = self:find("bg_fullscreen_01", self.AnimRoot)

	self.ToggleScrollView = self:find("ToggleScrollView", self.Left)
	self.TabToggle = self:find("TabToggle", self.Left)
	self.TabToggle:SetActive(false)

	local RightTop = self:find("RightTop", self.AnimRoot)
	self.CurrencyColumn = self:find("CurrencyColumn", RightTop)
	self.Currency = self:find("Currency", RightTop)
	self.Currency:SetActive(false)

	self.LoadingMask = self:find("LoadingMask", self.AnimRoot)

	self.BackButton = self:find("LeftTop/BackButton", self.AnimRoot)
	bee.addClick(self.BackButton, function()
		self:hideUI()
	end)

	self._currencyObjList = {}
end

function P:onStart()
	if self._params then
		self._selectSideTab = self._params.id
	end

	if ShopModel:getIsInitShopLimitList() then
		self.LoadingMask:SetActive(false)
		self:initToggleList()
		self:refreshToggle()
		self:refreshCenter()
	else
		self.LoadingMask:SetActive(true)
		self.ToggleScrollView:SetActive(false)

		ShopModel:initInfo()
	end
end

function P:evt_ItemChangeRSP()
	self:refreshCurrency()
end

function P:evt_SkinUnlockRSP()
	if self._curSubViewCls then
		self._curSubViewCls:refreshUI()
	end
end

function P:evt_updateShopLimit()
	if not self.tabtoggleList then
		self:initToggleList()
		self:refreshToggle()
		self:refreshCenter()
	end
	if self._curSubViewCls then
		self._curSubViewCls:refreshUI()
	end
end

function P:evt_updateShopPid()
	if self._curSubViewCls then
		self._curSubViewCls:refreshUI()
	end
end

function P:initToggleList()
	self.LoadingMask:SetActive(false)
	self.ToggleScrollView:SetActive(true)

	self.tabtoggleList = UiListEx:create(self.ToggleScrollView)
	self.tabtoggleList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.TabToggle)
	end)
	self.tabtoggleList:setRefreshFunc(function(data, item)
		self:setTabToggle(item, data)
	end)
	self.tabtoggleList:setWidth(160)
	self.tabtoggleList:setSpacing(5)
end

function P:refreshToggle()
	self._showList = ShopModel:getShopPushList()

	if not self._selectSideTab then
		self._selectSideTab = self._showList[1].cfg.id
	end

	self.tabtoggleList:setDatas(self._showList)
	self:refreshTabToggle()
end

function P:setTabToggle(item, data)
	local Ani_root = self:find("Ani_root", item)
	local ToggleIcon = self:find("ToggleIcon", Ani_root)
	local NameText = self:find("Mask/NameText", Ani_root)
	local HotTag = self:find("HotTag", Ani_root)

	data = data.cfg

	self:find("Mask/ImageCD", Ani_root):SetActive(data.time_limited == 1)
	bee.setIconInAtlas(ToggleIcon, data.tag_image, true)
	bee.setText(NameText, _T(data.name))

	if data.tag_tips then
		HotTag:SetActive(true)
		bee.setIconInAtlas(HotTag, _I(data.tag_tips), true)
	else
		HotTag:SetActive(false)
	end

	bee.removeAllClick(item)
	bee.addClick(item, function()
		Game:playSound("ui_tab_switch_1")
		bee.logEvent("hotsell-tab", data.id)
		if self._selectSideTab == data.id then
			return
		end
		self._selectSideTab = data.id
		self:refreshTabToggle()
		self:refreshCenter()
	end)
end

function P:refreshTabToggle()
	for k, v in pairs(self.tabtoggleList:getDatas()) do
		if v.node then
			if v.data.cfg.id == self._selectSideTab then
				-- self:playToggleInto(v.node)
				self:find("Ani_root", v.node).transform.localPosition = bee.v3(25, 0, 0)
				self:find("Ani_root/On", v.node):SetActive(true)
				self:find("Ani_root/Off", v.node):SetActive(true)
			else
				-- self:playToggleIdle2(v.node)
				self:find("Ani_root", v.node).transform.localPosition = bee.v3(0, 0, 0)
				self:find("Ani_root/On", v.node):SetActive(false)
				self:find("Ani_root/Off", v.node):SetActive(true)
			end
		end
	end
end

function P:refreshCenter()
	local cfg = tpl_shop_hot_sell[self._selectSideTab]
	if not cfg then
		return
	end

	local viewInfo
	if self._selectSideTab == 3 then
		viewInfo = SubView[self._selectSideTab][cfg.activity_id]
	elseif cfg.shop_type == 3 then
		-- 商店类型为3默认为复刻皮肤页签，复用30001的prefab
		viewInfo = SubView[30001]
	else
		viewInfo = SubView[self._selectSideTab]
	end

	if not viewInfo then
		return
	end

	if self._curSubView then
		CU.GameObject.Destroy(self._curSubView)
		self._curSubView = nil
	end

	self._curSubView = bee.createObj(viewInfo.view)
	self._curSubView.transform:SetParent(self.Center.transform, false)
	if viewInfo.pos then
		self._curSubView.transform.localPosition = bee.v3(viewInfo.pos[1], viewInfo.pos[2], 0)
	else
		self._curSubView.transform.localPosition = bee.v3(0, 0, 0)
	end
	self._curSubView.transform.localScale = bee.v3(1, 1, 1)
	self._curSubViewCls = ObjectPool:getCls(self._curSubView)
	self._curSubViewCls:setParams({id = self._selectSideTab, closeCb = function()
		self:refreshToggle()
	end})

	if cfg.shop_bg then
		bee.setIcon(self.Bg, cfg.shop_bg)
	end

	self:refreshCurrency()
end

function P:refreshCurrency()
	local cfg = tpl_shop_hot_sell[self._selectSideTab]
	if not cfg then
		return
	end

	local currencyList = {}
	if cfg.currency_bar then
		for i = 1, #cfg.currency_bar, 2 do
			table.insert(currencyList, {id = cfg.currency_bar[i], isAdd = cfg.currency_bar[i + 1]})
		end
	end
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
	local itemNum = ItemModel:getItemNumById(data.id)
	bee.setTextGold(CountText, _N2(itemNum))
	AddButton:SetActive(data.isAdd ~= 0)

	bee.removeAllClick(item)
	bee.addClick(item, function()
		if data.isAdd == 0 then
			return
		end
		UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(propCfg.id, true)})
	end)
	bee.addClick(self:find("ItemIcon", item), function()
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(data.id, true), target = self:find("ItemIcon", item)})
	end, true)
end

return P