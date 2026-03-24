local P = class("ShopExchange", UiBase)

function P:onAwake()
	self.ExchangeItem = self:find("ExchangeItem")
	self.ExchangeScrollList = self:find("ExchangeScrollList")
	self.ExchangeItem:SetActive(false)

	self._timeTag = {}
end

local ROW_COUNT = 4
function P:onStart()
	self.shop_type = self._params and self._params.shop_type or SHOP_TYPE.shop_exchange

	local rowPos = {}
	for i = 1, ROW_COUNT do
		if i == 1 then
			table.insert(rowPos, 190)
		else
			table.insert(rowPos, 380 * i - 190)
		end
	end

	self.exchangeList = UiListEx:create(self.ExchangeScrollList)
	self.exchangeList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.ExchangeItem)
	end)
	self.exchangeList:setRefreshFunc(function(data, item, isInit, index)
		self:setExchangeItem(item, data, isInit, index)
	end)
	self.exchangeList:setRowCount(ROW_COUNT)
	self.exchangeList:setRowPostions(rowPos)
	self.exchangeList:setWidth(510)

	local datas = ShopModel:getShopExchangeList(self.shop_type)
	self.exchangeList:setDatas(datas)

	self._musics = {}
	for _, v in ipairs(datas) do
		local exchange = ShopModel:getRewardsListWithType(v.cfg.props)[1]
		if exchange.major_type == GMajorType.PROP then
			local d = tpl_props[exchange.id]
			if d and (d.type == GPropKind.MusicLobby or d.type == GPropKind.MusicTable) then
				v.item_id = exchange.id
				table.insert(self._musics, v)
			end
		end
	end
end

function P:setExchangeItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local ItemBg = self:find("ItemBg", Ani_root)
	local CharacterMask = self:find("CharacterMask", Ani_root)
	local CharacterImg = self:find("CharacterMask/CharacterImg", Ani_root)
	local ItemIcon = self:find("ItemIcon", Ani_root)
	local ItemName = self:find("ItemName", Ani_root)
	local Price = self:find("Price", Ani_root)
	local CurrencyIcon = self:find("CurrencyIcon", Price)
	local PriceText = self:find("PriceText", Price)
	local LimitText = self:find("LimitText", Ani_root)
	local ViewButton = self:find("ViewButton", Ani_root)
	local Mask = self:find("Mask", Ani_root)
	local MaskText = self:find("Mask/MaskText", Ani_root)
	local CountText = self:find("CountBg/CountText", Ani_root)
	local TimeBg = self:find("TimeBg", Ani_root)
	local TimeText = self:find("TimeBg/TimeText", Ani_root)

	local cfg = data.cfg
	local exchange = ShopModel:getRewardsListWithType(cfg.props)[1]
	local exchangeCfg = ShopModel:getRewardCfg(exchange)

	if isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_2_ExchangeItem", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_TaskView_item_idle", Ani_root)
    end

    if self._timeTag[item] then
    	scheduler:removeTag(item)
    	self._timeTag[item] = nil
    end

    if cfg.time_end then
		TimeBg:SetActive(true)

		local leftTime = cfg.time_end - bee.getServerTime()
		if leftTime > 0 then
			bee.setText(TimeText, ShopModel:getShopTimeText(leftTime))
			self._timeTag[item] = self:schedule(1, function()
				leftTime = leftTime - 1
				if leftTime > 0 then
					bee.setText(TimeText, ShopModel:getShopTimeText(leftTime))
				else
					bee.setText(TimeText, _T("LAB_BACKPACK_DES_21"))
				end
			end)
		else
			bee.setText(TimeText, _T("LAB_BACKPACK_DES_21"))
		end
	else
		TimeBg:SetActive(false)
	end
	
	if exchange.major_type == GMajorType.PROP then
		ItemIcon:SetActive(true)
		CharacterMask:SetActive(false)
		bee.setIconInAtlas(ItemIcon, exchangeCfg.icon, true)
		bee.setText(ItemName, _T(exchangeCfg.name))
		bee.setIconInAtlas(ItemBg, "Shop[shop_exchange_gold_bg]")
	else
		ItemIcon:SetActive(false)
		CharacterMask:SetActive(true)
		local showSkin = get_tpl_subKey(tpl_character_skin_list, "role", exchange.id)[1]
		bee.setIconInAtlas(CharacterImg, showSkin.table_avatar_pic, true)
		bee.setText(ItemName, _T(exchangeCfg.name))
		bee.setIconInAtlas(ItemBg, "Shop[shop_exchange_gold_character_bg]")

		if bee.isIos or bee.isEditor then
			bee.convertMaskToSoftMask(CharacterMask)
		end
	end

	bee.setText(CountText, "x" .. _N(exchange.num))

	if exchange.major_type ~= GMajorType.PROP then
		LimitText:SetActive(false)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.DAILY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _T("LAB_SHOP_COMMON_11") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.WEEKLY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _T("LAB_SHOP_COMMON_12") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.MONTHLY then
		LimitText:SetActive(true)
		bee.setText(LimitText, _T("LAB_SHOP_COMMON_13") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.PERMANENT then
		LimitText:SetActive(true)
		bee.setText(LimitText, _T("LAB_SHOP_COMMON_14") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	else
		LimitText:SetActive(false)
	end

	if data.isOwn then
		Mask:SetActive(true)
		Price:SetActive(false)
		bee.setText(MaskText, _T("LAB_SHOP_COMMON_5"))
	elseif data.soldOut then
		Mask:SetActive(true)
		Price:SetActive(false)
		bee.setText(MaskText, _T("LAB_SHOP_COMMON_8"))
	else
		Mask:SetActive(false)
		Price:SetActive(true)

		local currency = tpl_props[cfg.exchange_cost[1]]
		bee.setIconInAtlas(CurrencyIcon, currency.icon)
		bee.setText(PriceText, cfg.exchange_cost[2])
	end

	local preViewType, itemData
	if exchange.major_type == GMajorType.PROP then
		itemData = ItemModel:getItem(exchange.id, true)
		if itemData.type == GPropKind.CardBack or itemData.type == GPropKind.Table or itemData.type == GPropKind.Title or itemData.type == GPropKind.CardFace then
			preViewType = 1
		elseif itemData.type == GPropKind.MusicLobby or itemData.type == GPropKind.MusicTable then
			preViewType = 2
		end
	elseif exchange.major_type == GMajorType.ROLE or exchange.major_type == GMajorType.ROLE_SKIN then
		preViewType = 3
	end
	if preViewType then
		ViewButton:SetActive(true)
	else
		ViewButton:SetActive(false)
	end

	local viewFunc = function()
		bee.logEvent("shop-goods-preview", cfg.shop_type, cfg.id)
		if preViewType == 1 then
			UiManager:showUI("BackpackPreview", {data = itemData})
		elseif preViewType == 2 then
			UiManager:showUI("BackpackMusic", {data = itemData, list = self._musics, cb = function(d)
				if d.item_id ~= itemData.item_id then
					local index = self.exchangeList:getIndex(d)
					self.exchangeList:moveToYItem(index, 0.2)
				end
			end})
		elseif preViewType == 3 then
			if exchange.major_type == GMajorType.ROLE then
				UiManager:showUI("CharacterMainProfile", {data = CharacterModel:getRoleData(exchange.id)})
			elseif exchange.major_type == GMajorType.ROLE_SKIN then
				local skinCfg = tpl_character_skin[exchange.id]
				UiManager:showUI("CharacterMainGarments", {data = CharacterModel:getRoleData(skinCfg.role), selectId = exchange.id})
			end
		end
	end

	local exchangeFunc = function()
		if data.soldOut then
			UiManager:showToast(_T("LAB_SHOP_COMMON_9"))
			return
		end
		if data.isOwn then
			if exchange.major_type == GMajorType.ROLE then
				UiManager:showToast(_T("LAB_SHOP_COMMON_36"))
			else
				UiManager:showToast(_T("LAB_SHOP_COMMON_16"))
			end
			return
		end
		if data.time_end and bee.getServerTime() > data.time_end then
			UiManager:showToast(_T("LAB_SHOP_COMMON_10"))
			self:refreshUI()
			return
		end
		Game:playSound("ui_button_confirm")
		if cfg.batch == 1 then
			UiManager:showUI("ShopExchangeBatch", {data = data})
		else
			UiManager:showUI("ShopExchangeSingle", {data = data})
		end
	end

	bee.removeAllClick(ViewButton)
	bee.addClick(ViewButton, function()
		viewFunc()
	end)

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		exchangeFunc()
	end)
end

function P:refreshUI()
	if not self.exchangeList then
		return
	end
	local datas = ShopModel:getShopExchangeList(self.shop_type)
	self.exchangeList:setDatas(datas)
end

