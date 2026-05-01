local P = class("StoryRecord", UiBase)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local Panel = self:find("Center/Panel", AnimRoot)
    
    self.TaskList = self:find("TaskList", Panel)
    self.Content = self:find("Viewport/Content", self.TaskList)
    self.Item1 = self:find("Item1", self.TaskList)
    self.Item2 = self:find("Item2", self.TaskList)
    self.Item1:SetActive(false)
    self.Item2:SetActive(false)

    self.Empty = self:find("Empty", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
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
                if name ~= "" then
                    bee.setText(self:find("TextName", item), name)
                else
                    self:find("TextName", item):SetActive(false)
                    self:find("ImageTitle", item):SetActive(false)
                end
                bee.setText(self:find("TextContent", item), _F(v.text, name))
            end
        end
    end
    self.Empty:SetActive(count == 0)
end

return P