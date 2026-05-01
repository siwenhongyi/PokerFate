local P = class("UiFilterBox")
UiFilterBox = P

-- 下拉选择框 button: 点击按钮 area: 下拉选择区域 parent: 显示下拉框的父节点
function P:ctor(button, area, parent)
    self.Button = button
    self.FilterArea = area
    self.FilterArea:SetActive(false)
    self.parent = parent

    -- 按钮的默认文本、显示下拉状态的箭头
    self.Text = bee.find("Text", self.Button)
    self.On = bee.find("On", self.Button)
    self.Off = bee.find("Off", self.Button)

    if self.Off then
        self.Off:SetActive(false)
    end
    if self.On then
        self.On:SetActive(true)
    end

    self.Item = bee.find("Item", self.FilterArea)
    if self.Item then
        self.Item:SetActive(false)
    end

    bee.addClick(self.Button, function()
        Game:playSound("ui_button_click")
        if self._disabled then
            return
        end
        self:setFilterShow()
    end, true)
end

-- 设置数据，datas: 字符串列表 idx: 默认选中项
function P:setDatas(datas, idx)
    self._datas = datas
    self._filterIdx = idx or 1

    self:_refreshSelect()
end

function P:setDisabled(flag)
    self._disabled = flag
end

-- 设置选中回调 fn(i, data)
function P:setSelectFunc(fn)
    self._selectFunc = fn
end

-- 设置创建节点的回调方法 fn(data)，返回元素节点
-- 默认使用 area 下的 Item 节点作为模板
function P:setCreateFunc(fn)
    self._createFunc = fn
end

-- 设置刷新节点的回调方法 fn(data, node)
function P:setRefreshFunc(fn)
    self._refreshFunc = fn
end

function P:setSelectIdx(idx)
    self._filterIdx = idx
    self:_refreshSelect()
end

function P:getSelectIdx()
    return self._filterIdx
end

function P:getFilterMask()
    if not self.FilterMask then
        local n = CU.GameObject("FilterMask")
        local cmp = n:AddComponent(typeof(CU.UI.Image))
        cmp.color = CU.Color(1, 1, 1, 0)
        n.transform:SetParent(self.parent.transform, false)
        n.transform.sizeDelta = bee.v2(SCREEN_WIDTH, SCREEN_HEIGHT)
        n:AddComponent(typeof(CU.UI.Button))
        self.FilterMask = n

        bee.addClick2(self.FilterMask, function()
            self:setFilterHide()
        end)

        self.FilterArea.transform:SetParent(self.FilterMask.transform, true)
    end
end

function P:setFilterHide()
    self.FilterArea:SetActive(false)
    if self.FilterMask then
        self.FilterMask:SetActive(false)
    end

    if self.Off then
        self.Off:SetActive(false)
    end
    if self.On then
        self.On:SetActive(true)
    end
end

function P:setFilterShow()
    self:getFilterMask()
    local flag = self.FilterArea.activeSelf
    self.FilterArea:SetActive(not flag)
    self.FilterMask:SetActive(not flag)

    if self.Off then
        self.Off:SetActive(not flag)
    end
    if self.On then
        self.On:SetActive(flag)
    end
    
    if not flag and not self._initFilter then
        self._initFilter = true
        self._filterItems = {}
        for i, v in ipairs(self._datas) do
            local item = nil
            if self._createFunc then
                item = self._createFunc(v)
                item.transform:SetParent(self.FilterArea.transform, false)
            elseif self.Item then
                item = CU.GameObject.Instantiate(self.Item, self.FilterArea.transform, false)
            end
            self._filterItems[i] = item
            item:SetActive(true)
            self:_refreshItem(i, v, item)
            bee.addClick(item, function()
                Game:playSound("ui_button_confirm")
                self:setFilterHide()

                if i ~= self._filterIdx then
                    self._filterIdx = i
                    self:_refreshSelect()
                end
            end)
        end
    elseif not flag then
        for i, item in ipairs(self._filterItems) do
            self:_refreshItem(i, self._datas[i], item)
        end
    end
end

function P:setFilterText(obj, idx)
    if idx == 1 then
        bee.setText(obj, _T("LAB_FRIROOM_034"))
    else
        bee.setText(obj, _F("LAB_FRIROOM_020", idx))
    end
end

function P:_refreshItem(i, v, item)
    if self._refreshFunc then
        self._refreshFunc(v, item)
    else
        bee.setText(bee.find("On/Text", item), v)
        bee.setText(bee.find("Off/Text", item), v)
        local On, Off = bee.find("On", item), bee.find("Off", item)
        if On then
            On:SetActive(self._filterIdx == i)
        end
        if Off then
            Off:SetActive(self._filterIdx ~= i)
        end
    end
end

function P:_refreshSelect()
    if self.Text then
        bee.setText(self.Text, self._datas[self._filterIdx])
    end
    if self._selectFunc then
        self._selectFunc(self._filterIdx, self._datas[self._filterIdx])
    end
end