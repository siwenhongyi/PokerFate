local P = class("VIPDetail", UiDialog)


function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    
    self.DetailList = self:find("DetailList", self.Panel)
    self.ItemTitle = self:find("ItemTitle", self.DetailList)
    self.ItemTitle:SetActive(false)
    self.Item1 = self:find("Item1", self.DetailList)
    self.Item1:SetActive(false)
    self.Item2 = self:find("Item2", self.DetailList)
    self.Item2:SetActive(false)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
end

function P:onShow()
    local datas = {}
    for _, v in ipairs(tpl_vip_exp_list_list) do
        table.insert(datas, {__kind = "title", data1 = v})
        for _, vv in ipairs(tpl_vip_exp_path_list) do
            if vv.group == v.id then
                local d = _G["tpl_" .. vv.shop][vv.product_id]
                if ShopModel:productIsCanShow(d) then
                    local byData = ShopModel:getPidData(d.buy_id)
                    if byData then
                        if v.type == 2 then
                            if datas[#datas].__kind == "item2" and not datas[#datas].data2 then
                                datas[#datas].data2 = vv
                            else
                                table.insert(datas, {__kind = "item2", data1 = vv})
                            end
                        else
                            table.insert(datas, {__kind = "item1", data1 = vv})
                        end
                    end
                end
            end
        end
    end

    self.ListDetail = UiListEx:create(self.DetailList)
    self.ListDetail:setWidth({
        title = 70,
        item1 = 120,
        item2 = 120,
    })
    self.ListDetail:setCreateFunc(function(data)
        if "title" == data.__kind then
            return CU.GameObject.Instantiate(self.ItemTitle)
        elseif "item1" == data.__kind then
            return CU.GameObject.Instantiate(self.Item1)
        end
        return CU.GameObject.Instantiate(self.Item2)
    end)
    self.ListDetail:setRefreshFunc(function(data, item)
        if "title" == data.__kind then
            bee.setText(self:find("Text", item), _T(data.data1.name))
        elseif "item1" == data.__kind then
            self:refreshItem(data.data1, self:find("Item1", item))
        else
            self:refreshItem(data.data1, self:find("Item1", item))
            self:refreshItem(data.data2, self:find("Item2", item))
        end
    end)
    self.ListDetail:setDatas(datas)
end

function P:refreshItem(data, item)
    if not data then
        item:SetActive(false)
        return
    end
    item:SetActive(true)

    local d = _G["tpl_" .. data.shop][data.product_id]
    local byData = ShopModel:getPidData(d.buy_id)

    bee.setText(self:find("TIPS", item), _F("LAB_VIP_TEXT_21", _T(d.name), byData.vip_exp))
    bee.setIcon(self:find("icon_item_01", item), d.icon)
end

