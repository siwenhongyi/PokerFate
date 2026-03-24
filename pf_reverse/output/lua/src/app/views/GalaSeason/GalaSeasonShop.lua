local P = class("GalaSeasonShop", require("app.views.GalaSeason.GalaSeasonBase"))

function P:onAwake()
    P.super.onAwake(self)
    self._tips = {"LAB_STORY_DIALOGUE_S2_1007_01","LAB_STORY_DIALOGUE_S2_1007_02","LAB_STORY_DIALOGUE_S2_1007_03"}

    self.ShopList = self:find("ShopList", self.Right)
    self.Item1 = self:find("Item1", self.ShopList)
    self.Item1:SetActive(false)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100705], true)

    local data = tpl_theme_activity[ThemeModel:getConfId()]
    
    self._datas = ShopModel:getShopExchangeList(data.shop_type)
    self._Items = {}

    self.ShopList:GetComponent("ScrollRect").enabled = false
    self:once(0.15, function()
        local Content = self:find("Viewport/Content", self.ShopList)
        for k, v in ipairs(self._datas) do
            local item = CU.GameObject.Instantiate(self.Item1, Content.transform, false)
            item:SetActive(true)
            self:refreshItem(v, item, k)
            self._Items[k] = item
        end
        self:once(0.7, function()
            self.ShopList:GetComponent("ScrollRect").enabled = true
        end)
    end)
	ShopModel:initInfo()
end

function P:refreshUI()
    local data = tpl_theme_activity[ThemeModel:getConfId()]
    self._datas = ShopModel:getShopExchangeList(data.shop_type)
    for k, v in ipairs(self._Items) do
        local data = self._datas[k]
        if data then
            self:refreshItem(data, v, 0)
        end
    end
end

function P:refreshItem(data, item, index)
    local Ani_root = self:find("Ani_root", item)

    if index > 0 then
        self:once(0.05 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_GalaSeasonShop_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_GalaSeasonShop_item_idle", Ani_root)
    end

    local d = ShopModel:getRewardCfg(data.cfg.props)
    if d then
        bee.setText(self:find("TextName", Ani_root), _T(d.name))
    elseif data.cfg.name then
        bee.setText(self:find("TextName", Ani_root), _T(data.cfg.name))
    end

    self:find("galaseason_shop_bg_sp_01", Ani_root):SetActive(data.cfg.is_special == 1)
    self:find("galaseason_shop_bg_sp_02", Ani_root):SetActive(data.cfg.is_special ~= 1)

    ShopModel:setShopLimitStr(self:find("TextLimit", Ani_root), data.cfg.limit_type, data.cfg.limit_count, data.buyCount)
    bee.setIcon(self:find("TextCount/Icon", Ani_root), tpl_props[data.cfg.exchange_cost[1]].icon)
    bee.setText(self:find("TextCount", Ani_root), _N(data.cfg.exchange_cost[2]))

    local d = tpl_props[data.cfg.props[2]]
    if d.type == GPropKind.Title then
        bee.setIcon(self:find("ImageTitle", Ani_root), d.icon)
        self:find("ImageIcon", Ani_root):SetActive(false)
        self:find("ImageTitle", Ani_root):SetActive(true)
    else
        bee.setIcon(self:find("ImageIcon", Ani_root), d.icon)
        self:find("ImageIcon", Ani_root):SetActive(true)
        self:find("ImageTitle", Ani_root):SetActive(false)
    end

    if data.cfg.limit_type and data.buyCount >= data.cfg.limit_count then
        self:find("TextCount", Ani_root):SetActive(false)
        self:find("TextSoldOut", Ani_root):SetActive(true)
        self:find("galaseason_shop_img_mask", Ani_root):SetActive(true)
    else
        self:find("TextCount", Ani_root):SetActive(true)
        self:find("TextSoldOut", Ani_root):SetActive(false)
        self:find("galaseason_shop_img_mask", Ani_root):SetActive(false)
    end
    local ViewButton = self:find("ViewButton", Ani_root)

    local itemData = tpl_props[data.cfg.props[2]]
    if itemData.preview == 1 then
        ViewButton:SetActive(true)
        bee.addClick2(ViewButton, function()
            ItemModel:onPreview(itemData)
        end, true)
    else
        ViewButton:SetActive(false)
    end

    bee.addClick2(item, function()
		Game:playSound("ui_button_confirm")
		if data.soldOut then
			UiManager:showToast(_T("LAB_SHOP_COMMON_9"))
			return
		end
        
        UiManager:showUI("GalaSeasonExchange", {data = data, isSingle = data.cfg.batch ~= 1})
    end, true)
end

function P:evt_updateShopLimit()
    self:refreshUI()
end

function P:evt_ItemChangeRSP(msg)
    local data = ThemeModel:getConfData()
    if not data then return end

    local storys = get_tpl_subKey(tpl_theme_storys_list, "group", data.storys)
    local items = {}
    for _, v in ipairs(storys) do
        if v.unlock_item then
            items[#items + 1] = v.unlock_item[1]
        end
    end
    for _, v in ipairs(msg.item_list) do
        if table.indexof(items, v.item_id) > 0 then
            bee.showUiTask("GalaSeasonHint", {item = v}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
            bee.runTask(POP_TAG.Reward)
            ThemeModel:refreshReddot()
            break
        end
    end
end

