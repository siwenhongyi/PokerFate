local P = class("ShopMonthlyCardReward", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")

    self.ItemList = self:find("ItemList", Center)
    self.Item1 = self:find("Item1", self.ItemList)
    self.Item1:SetActive(false)
    self.Content1 = self:find("Viewport/Content", self.ItemList)
    self.Content2 = self:find("Content", Center)

    bee.addClick2(self:find("common_panel_mask", Center), function()
        if self._params.cb then
            self._params.cb()
        end
        self:hideUI()
    end)

    self.TipsText = self:find("TipsText", Center)
	self.ButtonCont = self:find("ButtonCont", Center)
	self.ConfirmButton = self:find("ConfirmButton", self.ButtonCont)
	self.CancelButton = self:find("CancelButton", self.ButtonCont)

	bee.addClick(self.ConfirmButton, function()
        Game:playSound("ui_button_confirm")
		UiManager:showUI("ShopMonthlyCardPurchase")
	end)
	bee.addClick(self.CancelButton, function()
		self:hideUI()
	end)

    Game:playSound("ui_reward_gain")
end

local function _secondsToTimes(ts)
    local hour = math.floor(ts / 3600)
    local min = math.floor((ts % 3600) / 60)
    local sec = math.floor(ts % 3600 % 60)
    return hour .. ":" .. min .. ":" .. sec
end

function P:onShow()
    self._items = self._params.items
    self._musics = {}   -- 播放音乐列表

    self:once(0.5, function() self:_doShowAnim() end)

    local cardLeftTime = ShopModel:getMonthlyCardLeftTime()
    if not cardLeftTime or cardLeftTime == 0 then
        self.TipsText:SetActive(false)
        self.ButtonCont:SetActive(false)
        ShopModel:requestPayInfo()
	elseif cardLeftTime > tpl_constdata.Monthly_Card_Warn * 86400 then
		bee.setText(self.TipsText, _F("LAB_MONTHLY_CARD_17", math.floor(cardLeftTime / 86400)))
		self.ButtonCont:SetActive(false)
	elseif cardLeftTime > 86400 then
		bee.setText(self.TipsText, _F("LAB_MONTHLY_CARD_18", math.floor(cardLeftTime / 86400)))
		self.ButtonCont:SetActive(true)
	else
		bee.setText(self.TipsText, _F("LAB_MONTHLY_CARD_19", _secondsToTimes(cardLeftTime)))
		self:schedule(1, function()
			cardLeftTime = cardLeftTime - 1
			if cardLeftTime > 0 then
				bee.setText(self.TipsText, _F("LAB_MONTHLY_CARD_19", _secondsToTimes(cardLeftTime)))
			else
				bee.setText(self.TipsText, _T("LAB_MONTHLY_CARD_27"))
			end
		end)
		self.ButtonCont:SetActive(true)
	end
end

function P:_doShowAnim()
    local Content = self.Content1
    -- if #self._items <= 5 then
    --     Content = self.Content2
    -- end
    Content = self.Content2

    local items, itemKV, is_decompose = {}, {}, false
    for _, v in ipairs(self._items) do
        if v.is_decompose then
            is_decompose = true
        end
        if self:isMusicItem(v.org_item or v) then
            table.insert(self._musics, v.org_item or v)
        end
        local item = CU.GameObject.Instantiate(self.Item1, Content.transform, false)
        item:SetActive(true)
        local item1 = self:find("Item1", item)
        self:refreshItem(v, item1)
        -- item1:SetActive(false)
        -- table.insert(items, item1)
        item:SetActive(false)
        table.insert(items, item)
        itemKV[v] = item1
    end
    local s = self.ItemList.transform.sizeDelta
    for k, v in ipairs(items) do
        self:once(k * 0.15 + 0.2, function()
            if k > 5 then
                for _, vv in ipairs(items) do
                    vv.transform:SetParent(self.Content1.transform, false)
                end
            end
            v:SetActive(true)
            if k > 10 and (k - 1) % 5 == 0 then
                self:once(0.01, function()
                    local pos = bee.v3(self.Content1.transform.localPosition.x, 220 * (math.floor((k - 1) / 5) + 1) - s.y)
                    bee.tween(self.Content1)
                    : to(0.08, {position = pos})
                    : link()
                end)
            end

            if k == #items and is_decompose then
                self:once(0.5, function()
                    for _, vv in ipairs(self._items) do
                        if vv.is_decompose then
                            AnimationMgr:playUIEffect("Prefab/Eff_poker_fenjie", itemKV[vv].transform, bee.v3zero, 1, true)
                            self:_refreshItem(vv.decompose_item, itemKV[vv])
                        end
                    end
                    self:swapDecoposeItems(itemKV, false)
                end)
            end
        end)
    end
end

function P:swapDecoposeItems(itemKV, flag)
    self:once(3, function()
        for _, vv in ipairs(self._items) do
            if vv.is_decompose then
                bee.tween(itemKV[vv])
                : to(0.2, {alpha = 0})
                : call(function()
                    if flag then
                        self:_refreshItem(vv.decompose_item, itemKV[vv])
                    else
                        self:_refreshItem(vv.org_item or vv, itemKV[vv])
                    end
                end)
                : to(0.2, {alpha = 1})
                : link()
            end
        end
        self:swapDecoposeItems(itemKV, not flag)
    end)
end

function P:refreshItem(data, item)
    self:_refreshItem(data.org_item or data, item)

    -- if data.is_decompose then
    --     self:once(1, function()
    --         self:_refreshItem(data.decompose_item, item)
    --     end)
    -- end
end

function P:_refreshItem(data, item)
    local RoleItemObj = self:find("RoleItem", item)
    local PropItemObj = self:find("PropItem", item)
    local NewIcon = self:find("NewIcon", item)
    local ImagePlay = self:find("ImagePlay", item)

    local id = data.item_id or data.id

    NewIcon:SetActive(data.new)
    ImagePlay:SetActive(false)

    if data.major_type == GMajorType.ROLE or data.major_type == GMajorType.ROLE_SKIN then
        PropItemObj:SetActive(false)
        RoleItemObj:SetActive(true)
        RoleItem:create(RoleItemObj, data):bindDetail()
        self:find("common_item_grid_m_bg_01", item):SetActive(false)
        self:find("common_item_grid_m_bg_02", item):SetActive(false)
        self:find("common_item_grid_m_bg_03", item):SetActive(true)
    else
        PropItemObj:SetActive(true)
        RoleItemObj:SetActive(false)
        PropItem:create(PropItemObj, data):bindTips()

        local cfg = tpl_props[id]
        if cfg.type == GPropKind.MusicLobby or cfg.type == GPropKind.MusicTable then
            ImagePlay:SetActive(true)
            bee.addClick(ImagePlay, function()
                UiManager:showUI("BackpackMusic", {data = ItemModel:getItem(cfg.id, true), list = self._musics})
            end)
		end
        self:find("common_item_grid_m_bg_01", item):SetActive(cfg.quality <= 3)
        self:find("common_item_grid_m_bg_02", item):SetActive(cfg.quality == 4)
        self:find("common_item_grid_m_bg_03", item):SetActive(cfg.quality == 5)
    end
end

function P:isMusicItem(data)
    if data.major_type == GMajorType.ROLE or data.major_type == GMajorType.ROLE_SKIN then
        return false
    end

    local cfg = tpl_props[data.item_id or data.id]
    if cfg.type == GPropKind.MusicLobby or cfg.type == GPropKind.MusicTable then
        return true
    end
    return false
end

function P:evt_pay_sucess()
    self:hideUI()
end

return P