local P = class("HotSpringShop", require("app.views.Hotspring.HotSpringBase"))

function P:onAwake()
    P.super.onAwake(self)
    self._tips = {"LAB_STORY_DIALOGUE_S1_1008_01", "LAB_STORY_DIALOGUE_S1_1008_02", "LAB_STORY_DIALOGUE_S1_1008_03"}

    self.PiyoList = self:find("PiyoList", self.Right)
    self.Item = self:find("Item", self.PiyoList)
    self.Item:SetActive(false)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100805], true)

    local data = tpl_theme_activity[ThemeModel:getConfId()]
    
    self._datas = ShopModel:getShopExchangeList(data.shop_type)
    self._Items = {}

    self.PiyoList:GetComponent("ScrollRect").enabled = false
    self:once(0.15, function()
        local Content = self:find("Viewport/Content", self.PiyoList)
        for k, v in ipairs(self._datas) do
            local item = CU.GameObject.Instantiate(self.Item, Content.transform, false)
            item:SetActive(true)
            self:refreshItem(v, item, k)
            self._Items[k] = item
        end
        self:once(0.7, function()
            self.PiyoList:GetComponent("ScrollRect").enabled = true
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
            self:playAnimator("UI_2_HotSpringPlot_PiyoList", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_2_HotSpringPlot_PiyoList_idle", Ani_root)
    end

    if data.cfg.name then
        bee.setText(self:find("TextName", Ani_root), _T(data.cfg.name))
    else
        local d = ShopModel:getRewardCfg(data.cfg.props)
        bee.setText(self:find("TextName", Ani_root), _T(d.name))
    end
    ShopModel:setShopLimitStr(self:find("TextLimit", Ani_root), data.cfg.limit_type, data.cfg.limit_count, data.buyCount)
    bee.setIcon(self:find("hotspring_btn_yellow/Icon", Ani_root), tpl_props[data.cfg.exchange_cost[1]].icon)
    bee.setText(self:find("hotspring_btn_yellow/TextCount", Ani_root), _N(data.cfg.exchange_cost[2]))

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
        self:find("hotspring_btn_yellow", Ani_root):SetActive(false)
        self:find("item_commodity_sold_out", Ani_root):SetActive(true)
        self:find("Mask", Ani_root):SetActive(true)
    else
        self:find("hotspring_btn_yellow", Ani_root):SetActive(true)
        self:find("item_commodity_sold_out", Ani_root):SetActive(false)
        self:find("Mask", Ani_root):SetActive(false)
    end
    bee.addClick2(item, function()
		Game:playSound("ui_button_confirm")
		if data.soldOut then
			UiManager:showToast(_T("LAB_SHOP_COMMON_9"))
			return
		end
		if data.cfg.batch == 1 then
			UiManager:showUI("ShopExchangeBatch", {data = data})
		else
			UiManager:showUI("ShopExchangeSingle", {data = data})
		end
    end, true)
end

function P:evt_updateShopLimit()
    self:refreshUI()
end

