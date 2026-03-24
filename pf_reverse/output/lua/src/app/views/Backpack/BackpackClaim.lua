local P = class("BackpackClaim", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")

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
        self:refreshItem(data, item)
    end)
    
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)
end

function P:onShow()
    self._data = self._params.data
    local d = tpl_props[self._data.item_id]

    local datas = {}
    if d.accesses then
        for _, v in ipairs(d.accesses) do
            table.insert(datas, {id = v})
        end
    end
    self.ClaimList:setDatas(datas)
end

function P:refreshItem(data, item)
    local d = tpl_Jump_path[data.id]
    bee.setText(self:find("TextName", item), _T(d.name))
    bee.setText(self:find("TextGet", item), _T(d.button_text))
end

