local P = class("BunnyGirlShop", require("app.views.BunnyGirl.BunnyGirlBase"))

function P:onAwake()
    P.super.onAwake(self)
    self._tips = {"LAB_STORY_DIALOGUE_S4_1001_01","LAB_STORY_DIALOGUE_S4_1001_02","LAB_STORY_DIALOGUE_S4_1001_03"}

    self.ShopList = self:find("ShopList", self.Right)
    self.Line = self:find("Line01", self.ShopList)
    self.Item = self:find("Item1", self.ShopList)

    self.ShopContent = self:find("Viewport/Content", self.ShopList)
    self.ShopScrollRect = self.ShopList:GetComponent("ScrollRect")
    self.ShopScrollRect.enabled = false

    self.EvLineCount = 3
    self.ItemList = {}
    self.init = false
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100106], true)

    self.activityData = tpl_theme_activity[ThemeModel:getConfId()]
    self._datas = {}
    self:refreshUI()
end

function P:initShopItems()
    self:once(1, function()
        self.ShopScrollRect.enabled = true
    end)

    local totalCount = table.nums(self._datas)
    local lineCount = math.ceil (totalCount / self.EvLineCount)
    local remainCount = totalCount % self.EvLineCount
    local index = 0
    for i = 1, lineCount do
        local itemCount  = self.EvLineCount
        if i == lineCount and remainCount ~= 0 then
            itemCount = remainCount
        end
        local lineItem = CU.GameObject.Instantiate(self.Line, self.ShopContent.transform, false)
        lineItem:SetActive(true)
        local lineContent = self:find("Ani_root/Content", lineItem)
        for _ = 1, itemCount do
            index = index + 1
            local item = {}
            local propItem = CU.GameObject.Instantiate(self.Item, lineContent.transform, false)
            propItem:SetActive(true)
            item.go = propItem
            local itemRoot =  self:find("Ani_root", item.go)
            item.frame = self:find("bunnygirl_shop_bg_sp_01", itemRoot)
            item.icon = self:find("icon_gift_04_08", itemRoot)
            item.titleIcon = self:find("icon_title", itemRoot)
            item.costIcon = self:find("Price/bunnygirl_icon_champagne", itemRoot)
            item.price = self:find("Price/Value", itemRoot)
            item.limit = self:find("Limit/Text", itemRoot)
            item.name = self:find("ItemName", itemRoot)
            item.eyeBtn = self:find("bunnygirl_shop_btn_view", itemRoot)
            item.mask = self:find("bunnygirl_shop_img_mask", itemRoot)
            table.insert(self.ItemList, item)

            local time = 0
            time = index <= 12 and 0.1 * (index - 1) or (0.1 * 12)
            self:once(time, function()
                item.go:SetActive(true)
            end)
            item.go:SetActive(false)
        end
    end
end

function P:refreshUI()
    local activityDatas = ShopModel:getShopExchangeList(self.activityData.shop_type)
    self._datas = {}
    for _,v in pairs(activityDatas) do
        if v.cfg.activity == ThemeModel:getConfId() then
            table.insert(self._datas, v)
        end
    end

    if not self.init then
        self.init = true
        self:initShopItems()
    end

    local index = 0
    for _,v in pairs(self._datas) do
        index = index + 1
        self:refreshItem(v, index)
    end
end

function P:refreshItem(data, index)
    local item = self.ItemList[index]
    local itemCfg = tpl_props[data.cfg.props[2]]
    bee.setIcon(item.frame, data.cfg.is_special and "Bunnygirl[bunnygirl_shop_bg_sp_01]" or "Bunnygirl[bunnygirl_shop_bg_sp_02]")
    bee.setIcon(item.costIcon, ThemeModel:getThemeIcon())
    bee.setText(item.name, _T(itemCfg.name))
    local isTitle = itemCfg.type == GPropKind.Title
    item.icon:SetActive(not isTitle)
    item.titleIcon:SetActive(isTitle)
    if isTitle then
        bee.setIcon(item.titleIcon, itemCfg.icon)
    else
        bee.setIcon(item.icon, itemCfg.icon)
    end
    bee.setText(item.limit, _T("LAB_SHOP_COMMON_14") .. string.format(": %s/%s", data.buyCount, data.cfg.limit_count))
    bee.setText(item.price, data.cfg.exchange_cost[2])
    item.eyeBtn:SetActive(itemCfg.preview == 1)
    bee.addClick2(item.eyeBtn, function() ItemModel:onPreview(itemCfg) end, true)
    bee.addClick2(item.go, function()
        Game:playSound("ui_button_confirm")
		if data.soldOut then
			UiManager:showToast(_T("LAB_SHOP_COMMON_9"))
			return
		end
        UiManager:showUI("BunnyGirlExchange", {data = data, isSingle = data.cfg.batch ~= 1})
    end, true)
    item.mask:SetActive(data.soldOut)
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
            bee.showUiTask("BunnyGirlHint", {item = v}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
            bee.runTask(POP_TAG.Reward)
            ThemeModel:refreshReddot()
            break
        end
    end
end


function P:hideUI()
    P.super.hideUI(self)
    if self._is_show then
		self:hideTopUI()
	end
end

return P