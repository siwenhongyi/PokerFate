local P = class("SpringFestivalShop", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", self.AnimRoot)
    
    self.TimeText = self:find("Pannel/Time/Text", Center)
    self.CloseButton = self:find("Pannel/CloseButton", Center)
    self.PackList = self:find("Pannel/Pack/PackList", Center)

    self.PackScroll = self.PackList:GetComponent("ScrollRect")

    self.itemList = {}

    bee.addClick(self.CloseButton, function()
		Game:playSound("ui_button_confirm")
        -- self:onDispose()
		self:hideUI()
	end)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.SpringFestivalShop)
end

function P:onShow()
    P.super.onShow(self)

    if not (self._params and self._params.isAuto) then
        bee.logEvent("springfestival-shop")
    end

    self:countDown()
    self:initLuckyBagItems()
    self:refreshLuckyBagItems()
end

function P:countDown()
    SpringFestivalModel:getRemainTime(self.TimeText, self.node)
end

function P:evt_pay_sucess()
    bee.once(1, function ()
        self:refreshLuckyBagItems()
        SpringFestivalModel:reqTaskList()
    end)
end

function P:initLuckyBagItems()
    for i = 1, 3 do
        local itemGo = self.PackScroll.content:GetChild(i - 1).gameObject
        local item = ObjectPool:getCls(itemGo)
        self.itemList[i] = item
    end
end
function P:refreshLuckyBagItems()
    -- 排序
    local giftDic = {}
    for _,v in pairs(tpl_shop_activity_gifts) do
        local cid = 0
        if v.condition == nil then
            cid = v.id
        else
            cid = v.condition
        end
        if giftDic[cid] == nil then
                giftDic[cid] = {}
            end
        table.insert(giftDic[cid], v)
    end
    local showList = {}
    local buyedList = {}
    for _,v in pairs(giftDic) do
        table.sort(v, function(a, b) return a.index < b.index end)
        local count = table.nums(v)
        for i = 1, count do
            local buyCount = ShopModel:getLimitGoodsBoughtCount(v[i].shop_type, v[i].id)
            if buyCount < v[i].limit_count then
                table.insert(showList, v[i])
                break
            end
            if i == count then
                table.insert(buyedList, v[i])
            end
        end
    end

    table.sort(showList, function(a, b) return a.index < b.index end)
    table.sort(buyedList, function(a, b) return a.index < b.index end)
    local index = 0

    for _,v in pairs(showList) do
        index = index + 1
        local item = self.itemList[index]
        item:refreshItem(v, false, index)
    end
    for _,v in pairs(buyedList) do
        index = index + 1
        local item = self.itemList[index]
        item:refreshItem(v, true, index)
    end
    -- UiManager:showUI("ShopPurchaseTheme", {data = data})
end

-- function P:onDispose()
--     scheduler:removeTag(self.tag)
--     self.tag = nil
-- end

