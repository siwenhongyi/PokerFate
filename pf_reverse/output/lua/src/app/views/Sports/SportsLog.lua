local P = class("SportsLog", UiDialog)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local Center = self:find("Center", AnimRoot)
    self.Panel = self:find("AnimRoot/Center/Panel")
    
    self.ContentList = self:find("ContentList", self.Panel)
    self.Content = self:find("Viewport/Content", self.ContentList)
    self.Item1 = self:find("Item1", self.ContentList)
    self.Item2 = self:find("Item2", self.ContentList)
    self.Item1:SetActive(false)
    self.Item2:SetActive(false)
    self.itemList = {}

    self.Empty = self:find("Empty", Center)

    bee.addClick(self:find("sports_tc_btn_close", self.Panel), function()
        self:hideUI()
    end)

    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

function P:onShow()
    local data = StoryModel:getStoryData()
    local index = StoryModel:getCurIndex()
    local count = 0
    local sltIndex = 0
    local sltData = StoryModel:getSelectData()
    if data then
        for k, v in ipairs(data.nodes) do
            if k > index then
                break
            end

            if v.kind == 2001 and v.style == 0 then
                count = count + 1
                local item = CU.GameObject.Instantiate(0 == v.gender and self.Item1 or self.Item2, self.Content.transform, false)
                item:SetActive(true)
                local name = StoryModel:getTalkName(v)
                local hasTitle = name ~= ""
                if hasTitle then
                    bee.setText(self:find("Title/TextName", item), name)
                else
                    self:find("Title", item):SetActive(false)
                end
                bee.setText(self:find("Content/TextContent", item), _F(v.text, name))
                table.insert(self.itemList, {item = item, title = hasTitle})
            end

            if v.kind == 4002 then
                sltIndex = sltIndex + 1
                local tab = sltData[sltIndex]
                if tab then
                    local item = CU.GameObject.Instantiate(self.Item2, self.Content.transform, false)
                    item:SetActive(true)
                    self:find("Title", item):SetActive(false)
                    bee.setText(self:find("Content/TextContent", item), _T(sltData[sltIndex]))
                    table.insert(self.itemList, {item = item, title = false})
                end
            end
        end
        self:setItemsDetailSize()
    end
    self.Empty:SetActive(count == 0)
end

function P:setItemsDetailSize()
    bee.once(0.02, function ()
        for _,v in pairs(self.itemList) do
            local itemTran = v.item:GetComponent("RectTransform")
            local contentTran = self:find("Content", v.item):GetComponent("RectTransform")
            -- CU.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(contentTran)
            if not v.title then
                contentTran.anchoredPosition = bee.v2(0, 0)
                local verGroup = contentTran:GetComponent("VerticalLayoutGroup")
                verGroup.padding.top = 30
            end
            itemTran.sizeDelta = bee.v2(itemTran.sizeDelta.x, contentTran.sizeDelta.y + (v.title and 40 or 5))
        end
    end)
end

return P