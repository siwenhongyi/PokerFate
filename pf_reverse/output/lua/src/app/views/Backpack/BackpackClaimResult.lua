local P = class("BackpackClaimResult", UiDialog)

function P:onAwake()
    self._closeAnim = ""
    
    local Center = self:find("AnimRoot/Center")

    self.ItemList = self:find("ItemList", Center)
    self.Item1 = self:find("Item1", self.ItemList)
    self.Item1:SetActive(false)
    self.Content1 = self:find("Viewport/Content", self.ItemList)
    self.Content2 = self:find("Content", Center)
    self.TitleText = self:find("common_result_title/TitleText", Center)

    bee.addClick2(self:find("common_panel_mask", Center), function()
        if self._params.delay and math.abs(os.time() - self._startDt) < self._params.delay then
            return
        end
        if self._params.cb then
            self._params.cb()
        end
        self:hideUI()
        ItemModel:refreshReddot()
        bee.emit("evt_BackpackClaimResultClose")
    end)

    Game:playSound("ui_reward_gain")
end

function P:onShow()
    if not self._params.items then
        return
    end

    self._startDt = os.time()

    -- 合并道具
    self._items = {}
    for k,v in pairs(self._params.items) do
        -- 判断是否为新道具
        local d = v.org_item or v
        if not d.major_type or d.major_type == GMajorType.PROP then
            d.new = ItemModel:checkIsNewItem(d.item_id or d.id, true)
        end
        if v.decompose_item then
            v.decompose_item.new = ItemModel:checkIsNewItem(d.item_id or d.id, true)
        end

        local isIn = false
        for k1, v1 in pairs(self._items) do
            local d1 = v1.org_item or v1
            if v.decompose_item and v.decompose_item.item_id and v.decompose_item.item_id > 0 then
            else
                -- 分解道具不合并
                if d.item_id and d1.item_id == d.item_id then
                    d1.num = d.num + d1.num
                    isIn = true
                    break
                end
            end
        end
        if not isIn then
            table.insert(self._items, v)
        end
    end

    if not self._items then
        return
    end

    -- 排序
    local PropsTypeSort = {}
    for k, v in ipairs(tpl_constdata.PropsTypeSort) do
        PropsTypeSort[v] = k
    end
    for _, v in ipairs(self._items) do
        local d = v.org_item or v
        v.__tmpType = tpl_props[d.item_id or d.id] and tpl_props[d.item_id or d.id].type or -1
        if not d.major_type then
            d.major_type = GMajorType.PROP
        end
    end
    table.sort(self._items, function(a, b)
        local sumA = 10000
        local sumB = 10000
        if a.major_type == GMajorType.ROLE then
            sumA = 1000000
        end
        if b.major_type == GMajorType.ROLE then
            sumB = 1000000
        end
        if a.major_type == GMajorType.ROLE_SKIN then
            sumA = 100000
        end
        if b.major_type == GMajorType.ROLE_SKIN then
            sumB = 100000
        end

        local a1, b1 = a.org_item or a, b.org_item or b
        if a1.major_type == GMajorType.PROP and b1.major_type == GMajorType.PROP then
            if PropsTypeSort[a.__tmpType] > PropsTypeSort[b.__tmpType] then
                sumA = sumA + 1000
            else
                sumB = sumB + 1000
            end
            if tpl_props[a1.item_id or a1.id].type > tpl_props[b1.item_id or b1.id].type then
                sumA = sumA + 100
            else
                sumB = sumB + 100
            end
            if tpl_props[a1.item_id or a1.id].bagIndex > tpl_props[b1.item_id or b1.id].bagIndex then
                sumA = sumA + 10
            else
                sumB = sumB + 10
            end
        end

        if (a1.item_id or a1.id) < (b1.item_id or b1.id) then
            sumA = sumA + 1
        else
            sumB = sumB + 1
        end

        return sumA > sumB
    end)

    self._musics = {}   -- 播放音乐列表

    self:once(0.1, function()
        self:_doShowAnim()
    end)
    self:once(0.5, function()
        bee.vibrate(tpl_vibrate.shock_award)
    end)

    if self._params and self._params.title then
        bee.setIcon(self.TitleText, _I(self._params.title))
    end
end

function P:_doShowAnim()
    local Content = self.Content1
    if #self._items <= 5 then
        self.ItemList:SetActive(false)
    end
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
                Game:playSound("ui_button_confirm")
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

