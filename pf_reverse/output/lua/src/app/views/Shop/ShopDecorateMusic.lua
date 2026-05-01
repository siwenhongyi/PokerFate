local P = class("ShopDecorateMusic", UiBase)

local FilterTypeInfo = {
	[14] = {
		[1] = {name = "TAB_SHOP_THEME_3"},
		[2] = {propType = GPropKind.MusicLobby, name = "TAB_SHOP_THEME_4"},
		[3] = {propType = GPropKind.MusicTable, name = "TAB_SHOP_THEME_5"},
	},
	[18] = {
		[1] = {name = "TAB_SHOP_THEME_3"},
		[2] = {propType = GPropKind.AllInEff, name = "TAB_SHOP_DECORATION_12"},
		[3] = {propType = GPropKind.NameplateEff, name = "TAB_SHOP_DECORATION_13"},
	},
}

function P:onAwake()
	self.Item1 = self:find("Item1")
	self.ItemList = self:find("ItemList")
	self.Item1:SetActive(false)

	self.MusicFilter = self:find("MusicFilter")
	self.FilterButton = self:find("FilterButton", self.MusicFilter)
	self.ArrowButton = self:find("ArrowButton", self.FilterButton)
	self.Arrow = self:find("Arrow", self.ArrowButton)
	self.FilterText = self:find("FilterText", self.FilterButton)
	self.MusicDropDown = self:find("MusicDropDown", self.MusicFilter)
	self.DropDownItem = self:find("DropDownItem", self.MusicDropDown)
	self.DropDownItem:SetActive(false)
	self.FilterMask = self:find("FilterMask", self.MusicDropDown)
	self.filterItemList = {}
	self.MusicDropDown:SetActive(false)

	self._timeTags = {}

	bee.addClick(self.FilterButton, function()
		Game:playSound("ui_button_confirm")
		self:openFilterDropDown()
	end)
	bee.addClick(self.ArrowButton, function()
		Game:playSound("ui_button_confirm")
		self:openFilterDropDown()
	end)
	bee.addClick2(self.FilterMask, function()
		self:closeFilterDropDown()
	end)
end

function P:onStart()
	self._selectFilterId = 1
	self._filterTypeInfo = FilterTypeInfo[self._params.shop_type]

	self.shopItemList = UiListEx:create(self.ItemList)
	self.shopItemList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item1)
	end)
	self.shopItemList:setRefreshFunc(function (data, item, isInit, index)
		self:setShopItem(item, data, isInit, index)
	end)
	self.shopItemList:setRowCount(2)
	self.shopItemList:setRowPostions({-358, 395})
	self.shopItemList:setWidth(390)

	self:setShopList()

	self:initFilterCont()

	ShopModel:refreshNewItemByShopType(self._params.shop_type, true)
	ShopModel:refreshTimeLimitItemByShopType(self._params.shop_type, true)
	ShopModel:refreshShopNewTag(self._params.shop_type)
end

function P:refreshUI()
	self:setShopList()
end

function P:setShopList()
	self.dataList = ShopModel:getDecorateList(self._params.shop_type, self._filterTypeInfo[self._selectFilterId].propType, true)
	self.shopItemList:setDatas(self.dataList)
end

function P:setShopItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local ItemBg = self:find("ItemBg", Ani_root)
	local ItemIcon = self:find("ItemIcon", ItemBg)
	local Mask = self:find("Mask", Ani_root)
	local ShowImg = self:find("Mask/ShowImg", Ani_root)
	local NameText = self:find("NameText", Ani_root)
	local PreviewButton = self:find("PreviewButton", Ani_root)
	local PreviewIcon = self:find("PreviewButton/PreviewIcon", Ani_root)
	local MusicPreviewIcon = self:find("PreviewButton/MusicPreviewIcon", Ani_root)
	local NewTag = self:find("NewTag", Ani_root)
	local Pri = self:find("Pri", Ani_root)
	local PriText = self:find("Pri/PriText", Ani_root)
	local PriIcon = self:find("Pri/PriIcon", Ani_root)
	local OwnTag = self:find("OwnTag", Ani_root)
	local ButtonGo = self:find("ButtonGo", Ani_root)
	local CountDown = self:find("CountDown", Ani_root)
	local CountDown1 = self:find("CountDown1", Ani_root)
	local Discount = self:find("Discount", Ani_root)
	local DiscountText = self:find("DiscountText", Discount)

	if isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_2_ShopDecorateTheme", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_TaskView_item_idle", Ani_root)
    end

    local cfg = data.cfg
    local propCfg = tpl_props[cfg.props[1]]
    if propCfg.type == GPropKind.MusicLobby or propCfg.type == GPropKind.MusicTable then
    	MusicPreviewIcon:SetActive(true)
    	PreviewIcon:SetActive(false)
    else
    	MusicPreviewIcon:SetActive(false)
    	PreviewIcon:SetActive(true)
    end
	if ItemModel.DecorateCfg[propCfg.type] then
		Mask:SetActive(true)
		ItemBg:SetActive(false)
		local decCfg = ItemModel.DecorateCfg[propCfg.type][propCfg.mapId]
		bee.setIconInAtlas(ShowImg, decCfg.bg_small, true)
	elseif propCfg.type == GPropKind.NameplateEff then
		Mask:SetActive(false)
		ItemBg:SetActive(true)
		bee.setIconInAtlas(ItemIcon, propCfg.icon)
		ItemIcon.transform.localScale = bee.v3(1, 1, 1)
	else
		Mask:SetActive(false)
		ItemBg:SetActive(true)
		bee.setIconInAtlas(ItemIcon, propCfg.icon)
		ItemIcon.transform.localScale = bee.v3(0.8, 0.8, 1)
	end

	bee.setText(NameText, _T(propCfg.name))
	bee.setIconInAtlas(PriIcon, tpl_props[cfg.pri[1]].icon)
	bee.setText(PriText, cfg.pri[2])

	NewTag:SetActive(ShopModel:isShowNewTag(cfg))

	if cfg.time_end then
		local leftTime = cfg.time_end - bee.getServerTime()
		if leftTime > 0 then
			self:_setTimeShow(Ani_root, leftTime)
			self._timeTags[item] = bee.schedule(1, function()
				leftTime = leftTime - 1
				self:_setTimeShow(Ani_root, leftTime)
			end, item)
		else
			self:_setTimeShow(Ani_root, leftTime)
		end
	else
		CountDown:SetActive(false)
		CountDown1:SetActive(false)
	end

	if cfg.relation_gift and not data.isOwn then
		ButtonGo:SetActive(true)
		Discount:SetActive(true)
		if cfg.relation_gift[1] == SHOP_TYPE.shop_theme then
			local discount = tpl_shop_theme[cfg.relation_gift[2]].discount
			bee.setText(DiscountText, ((1000 - discount) / 10) .. "%")
		end
	else
		ButtonGo:SetActive(false)
		Discount:SetActive(false)
	end

	OwnTag:SetActive(data.isOwn)
	Pri:SetActive(not data.isOwn)

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		if cfg.new_tag == 1 then
			NewTag:SetActive(false)
			ShopModel:setNewItem(cfg)
		end

		if data.isOwn then
			UiManager:showToast(_T("LAB_SHOP_COMMON_16"))
			return
		end
		Game:playSound("ui_button_confirm")
		UiManager:showUI("ShopExchangeSingle", {data = data})
	end)

	bee.removeAllClick(ButtonGo)
	bee.addClick(ButtonGo, function()
		bee.logEvent("shop-theme-link", data.shop_type, data.id)
		Game:playSound("ui_button_confirm")
		if cfg.new_tag == 1 then
			NewTag:SetActive(false)
			ShopModel:setNewItem(cfg)
		end

		ItemModel:jumpView(106001, cfg.relation_gift[2])
	end)

	-- 道具预览
	bee.removeAllClick(PreviewButton)
	bee.addClick(PreviewButton, function()
		bee.logEvent("shop-goods-preview", data.shop_type, data.id)
		Game:playSound("ui_button_confirm")
		if cfg.new_tag == 1 then
			NewTag:SetActive(false)
			ShopModel:setNewItem(cfg)
		end

		if propCfg.type == GPropKind.AllInEff then
			local themeInfo = PlayerModel:getCurScheme()
			local skinCfg = tpl_character_skin[themeInfo.skin_id]
			UiManager:showUI(GameModel:getAllinUiName(propCfg.id), {role = CharacterModel:getRoleData(skinCfg.role), skin = skinCfg})
		elseif propCfg.type == GPropKind.LobbyScene then
			UiManager:showUI("BackpackLobbyPreview", {data = propCfg, list = {propCfg}})
		elseif propCfg.type == GPropKind.MusicLobby or propCfg.type == GPropKind.MusicTable then
			local list = {}
			for k,v in pairs(self.dataList) do
				table.insert(list, ItemModel:getItem(v.cfg.props[1], true))
			end
			UiManager:showUI("BackpackMusic", {data = ItemModel:getItem(cfg.props[1], true), list = list, isShop = true})
		else
			UiManager:showUI("BackpackPreview", {data = propCfg})
		end
	end)
end

function P:initFilterCont()
	for i, v in ipairs(self._filterTypeInfo) do
		local copyItem = CU.GameObject.Instantiate(self.DropDownItem)
		copyItem.transform:SetParent(self.MusicDropDown.transform)
		copyItem.transform.localPosition = bee.v3(0, 0, 0)
		copyItem.transform.localScale = bee.v3(1, 1, 1)
		copyItem:SetActive(true)

		bee.setText(self:find("Item/On/Text", copyItem), _T(v.name))
		bee.setText(self:find("Item/Off/Text", copyItem), _T(v.name))

		bee.removeAllClick(self:find("Item", copyItem))
		bee.addClick(self:find("Item", copyItem), function()
			Game:playSound("ui_button_confirm")
			bee.logEvent("shop-bmg-option", i - 1)
			if self._selectFilterId == i then
				return
			end

			self._selectFilterId = i
			self:setShopList()
			self:refreshFilterCont()

			self:closeFilterDropDown()
		end)
	end

	self:refreshFilterCont()
end

function P:refreshFilterCont()
	for k, v in pairs(self.filterItemList) do
		self:find("Item/On", v):SetActive(self._selectFilterId == k)
		self:find("Item/Off", v):SetActive(self._selectFilterId ~= k)
	end
	bee.setText(self.FilterText, _T(self._filterTypeInfo[self._selectFilterId].name))
end

local openAngles = bee.v3(0, 0, 0)
function P:openFilterDropDown()
	self.Arrow.transform.localEulerAngles = openAngles
	self.MusicDropDown:SetActive(true)
end

local closeAngles = bee.v3(0, 0, 180)
function P:closeFilterDropDown()
	self.Arrow.transform.localEulerAngles = closeAngles
	self.MusicDropDown:SetActive(false)
end

function P:_setTimeShow(item, leftTime)
	local CountDown = self:find("CountDown", item)
	local CountDown1 = self:find("CountDown1", item)
	if leftTime > 259200 then
		CountDown:SetActive(true)
		CountDown1:SetActive(false)
		bee.setText(self:find("TimeText", CountDown), ShopModel:getShopTimeText(leftTime))
	elseif leftTime > 0 then
		-- 小于3天
		CountDown:SetActive(false)
		CountDown1:SetActive(true)
		bee.setText(self:find("TimeText", CountDown1), ShopModel:getShopTimeText(leftTime))
	else
		CountDown:SetActive(false)
		CountDown1:SetActive(true)
		bee.setText(self:find("TimeText", CountDown1), _T("LAB_BACKPACK_DES_21"))
	end
end

return P