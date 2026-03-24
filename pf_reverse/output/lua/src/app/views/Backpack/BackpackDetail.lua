local P = class("BackpackDetail", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    self.ClickMask = self:find("AnimRoot/common_panel_mask_70")
    self.TextNum = self:find("common_panel_notice_grid_01/TextNum", Center)
    self.TextDec = self:find("TextScrollView/Viewport/Content/TextDec", Center)
    self.TextName = self:find("TextName", Center)
    self.PropItemObj = self:find("PropItem", Center)

    local ClaimList = self:find("ClaimList", Center)
    self.Item1 = self:find("Item1", ClaimList)
    self.Item1:SetActive(false)

    bee.addClick(self:find("CloseButton", Center), function()
        self:hideUI()
    end)

    self.ClaimList = UiListEx:create(self:find("ClaimList", Center))
    self.ClaimList:setWidth(130)
    self.ClaimList:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ClaimList:setRefreshFunc(function(data, item)
        if data.__kind == 1 then
            self:refreshItem(data, item)
        else
            self:refreshUseItem(data, item)
        end
    end)

    bee.addClick2(self.ClickMask, function()
        self:hideUI()
    end)
end

function P:onShow()
    self._data = self._params.data
    local d = tpl_props[self._data.item_id]
    bee.setText(self.TextName, _T(d.name))
    bee.setText(self.TextDec, ItemModel:getItemDesText(d.id))
    bee.setText(self.TextNum, string.format("<color=#ffffff>%s</color> %d", _T("LAB_PROPS_TEXT_1"), self._data.num))
    PropItem:create(self.PropItemObj, self._data):hideNum()

    local datas = {}
    if d.accesses then
        for _, v in ipairs(d.accesses) do
            local jumpCfg = tpl_Jump_path[v]
            local isShowUse = false
            if jumpCfg.view == "BackpackMain" then
                -- 跳转到自选礼盒 - 判断是否显示快捷使用
                local jumpPropCfg = tpl_props[jumpCfg.select]
                if jumpPropCfg and jumpPropCfg.type == GPropKind.OptionalBox then
                    if ItemModel:getItemNumById(jumpPropCfg.id) > 0 then
                        isShowUse = true
                        table.insert(datas, {id = v, __kind = 2})
                    end
                end
            end
            if not isShowUse then
                table.insert(datas, {id = v, __kind = 1})
            end
        end
    end
    self.ClaimList:setDatas(datas)
end

function P:refreshItem(data, item)
    local d = tpl_Jump_path[data.id]
    bee.setText(self:find("TextName", item), _T(d.name))
    bee.setText(self:find("ClaimButton/TextGet", item), _T(d.button_text))

    bee.addClick(self:find("ClaimButton", item), function()
        ItemModel:jumpView(data.id, self._data.item_id)
        if self._params and self._params.jumpCb then
            self._params.jumpCb(data.id)
        end
        self:hideUI()
    end, true)
end

function P:refreshUseItem(data, item)
    local d = tpl_Jump_path[data.id]
    bee.setText(self:find("TextName", item), _T(d.name))
    bee.setText(self:find("ClaimButton/TextGet", item), _T("LAB_PATH_BUTTON_TEXT_2"))

    bee.addClick(self:find("ClaimButton", item), function()
        UiManager:showUI("BackpackGift", {id = d.select, characterId = self._params.characterId})
        self:hideUI()
    end, true)
end

