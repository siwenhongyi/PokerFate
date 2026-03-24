local P = class("GachaModel", BaseModel)

function P:ctor(logic)
	self.saveData = {
        _skip_flag = false
    }
	self._cardPoolList = {}
	self._cardPoolMap = {}

	P.super.ctor(self)
end

function P:afterLogin()
	self._cardPoolList = {}
	self._cardPoolMap = {}
end

function P:initGachaPoolList(force, checkIsNewPool)
    if next(self._cardPoolList) and not force then
        return
    end
	Net:post("/draw/list", nil, function(data)
		if not data or not data.list then
			return
		end

        local isNewCardPool = false
        if checkIsNewPool then
            if #self._cardPoolList ~= #data.list then
                isNewCardPool = true
            else
                for _, v in pairs(self._cardPoolList) do
                    local isIn = false
                    for _, v1 in pairs(data.list) do
                        if v1.pool_id == v.pool_id then
                            isIn = true
                            break
                        end
                    end
                    if not isIn then
                        isNewCardPool = true
                    end
                end
                if not isNewCardPool then
                    for _, v in pairs(data.list) do
                        local isIn = false
                        for _, v1 in pairs(self._cardPoolList) do
                            if v1.pool_id == v.pool_id then
                                isIn = true
                                break
                            end
                        end
                        if not isIn then
                            isNewCardPool = true
                        end
                    end
                end
            end
        end

		self._cardPoolList = data.list
        table.sort(self._cardPoolList, function(a, b) return a.sort < b.sort end)

		self._character_rate = {}
		self._cosmetic_rate = {}
		self._item_rate = {}
		self._cardPoolMap = {}
		for k, v in pairs(self._cardPoolList) do
            self._character_rate[v.pool_id] = v.character_rate
            self._cosmetic_rate[v.pool_id] = v.cosmetic_rate
            self._item_rate[v.pool_id] = v.item_rate
			self._cardPoolMap[v.pool_id] = self:setCardPoolList(v)
		end

        bee.emit("evt_gachaUpdate", {isNew = isNewCardPool})
	end)
end

function P:setCardPoolList(data)
    local list = data.list
    local totalWeightList = {}
    for k,v in pairs(list) do
        if not totalWeightList[v.content_type] then
            totalWeightList[v.content_type] = v.weight
        else
            totalWeightList[v.content_type] = totalWeightList[v.content_type] + v.weight
        end
    end
    for k,v in pairs(list) do
        v.probability = string.format("%.4f", v.weight / totalWeightList[v.content_type])
        local rate
        if v.content_type == CARD_CONTENT_TYPE.CHARACTER then
            rate = data.character_rate
        elseif v.content_type == CARD_CONTENT_TYPE.DECORATION then
            rate = data.cosmetic_rate
        elseif v.content_type == CARD_CONTENT_TYPE.GIFT then
            rate = data.item_rate
        end
        v.totalRate = (rate / 10000) * (v.weight / 10000)
        v.totalRate = math.floor(v.totalRate * 1000) / 1000
    end
    return list
end

-- 招募一次
function P:recruitOne(pool_id, costList, cb)
    if not costList then
        return
    end

    self:drawCard(pool_id, 1, costList, function(data)
        if cb then
        	cb()
        end
    end)

    return true
end

-- 招募十次
function P:recruitTen(pool_id, costList, cb)
    if not costList then
        return
    end

    self:drawCard(pool_id, 10, costList, function(data)
        if cb then
        	cb()
        end
    end)

    return true
end

function P:drawCard(id, num, costList, cb)
	local args = {}
	args.pool_id = id
	args.num = num
	args.item_map = {}
	for k,v in pairs(costList) do
		args.item_map[tostring(v.id)] = v.count
	end

	Net:post("/draw/card", args, function(data)
		if not data or not data.list then
			return
		end

        local kind = CARD_CONTENT_TYPE.GIFT
        local roleNewList = {}
        local propNewList = {}
        local showList = {}
        for i, v in ipairs(data.list) do
            v.id = v.content_id
            if v.content_type == CARD_CONTENT_TYPE.CHARACTER then
                v.major_type = GMajorType.ROLE
                v.new = v.is_new_role
                kind = v.content_type
            elseif v.content_type == CARD_CONTENT_TYPE.DECORATION then
                v.major_type = GMajorType.PROP
                v.new = ItemModel:checkIsNewItem(v.content_id, true) and propNewList[v.id] ~= 1
                propNewList[v.id] = 1
                if kind ~= CARD_CONTENT_TYPE.CHARACTER then
                    kind = v.content_type
                end
            else
                v.major_type = GMajorType.PROP
                v.new = ItemModel:checkIsNewItem(v.content_id, true) and propNewList[v.id] ~= 1
                propNewList[v.id] = 1
            end

            table.insert(showList, v)
        end

        if self:getSkipAnimFlag() then
            UiManager:showUI("GachaResultShow", {showList = showList, closeCb = function()
                UiManager:showUI("GachaResult", {pool_id = id, num = num, list = data.list})
            end})
        else
            self:showWheelAnim(kind, function()
                UiManager:showUI("GachaResultShow", {showList = showList, closeCb = function()
                    UiManager:showUI("GachaResult", {pool_id = id, num = num, list = data.list})
                end})
            end)
        end

		if cb then
			cb()
		end
	end)
end

function P:showWheelAnim(kind, cb)
    UiManager:hideUI("GachaResult")
    UiManager:showUI("GachaWheelMask", {
        closeCb = cb,
        kind = kind,
    })
end

function P:getCardPoolList()
	return self._cardPoolList
end

function P:getCardPoolListById(id)
	return self._cardPoolMap[id]
end

function P:getCardPoolCharacterRate(id)
	return self._character_rate[id] and (self._character_rate[id] / 100) or 0
end

function P:getCardPoolCosmeticRate(id)
	return self._cosmetic_rate[id] and (self._cosmetic_rate[id] / 100) or 0
end

function P:getCardPoolItemRate(id)
	return self._item_rate[id] and (self._item_rate[id] / 100) or 0
end

function P:setSkipAnimFlag(flag)
    self.saveData._skip_flag = flag
    self:onSave()
end

function P:getSkipAnimFlag()
    return self.saveData._skip_flag
end

function P:evt_NoticeBRC(params)
    if params.type == tpl_PushConsts.DRAW_CARD_CONF.code then
        self:initGachaPoolList(true, true)
    end
end

function P:getContainCardPoolId(id)
    for _, cardPool in ipairs(self._cardPoolList) do
        for _, v in pairs(cardPool.list) do
            if v.content_id == id then
                return cardPool.pool_id
            end
        end
    end
end

-- 跨天
function P:evt_serverTimeCrossDay()
    bee.once(math.random(1, 60), function()
        self:initGachaPoolList(true, true)
    end)
end

