local P = class("NoticeModel", BaseModel)

function P:ctor()
    self.saveData = {
        cloud = {
            -- reads .. uid = {},
        }
    }

    P.super.ctor(self)

    self.NOTICE_TYPE = {
        Activity = 1,
        System = 2,
    }

    self._notices = {
        [self.NOTICE_TYPE.Activity] = {
            total = 0,
            unread_total = 0,
            list = {},
        },
        [self.NOTICE_TYPE.System] = {
            total = 0,
            unread_total = 0,
            list = {},
        },
    }

    self._haveNew = nil
    self._curLan = nil
    self._reads = nil
end

function P:afterInit()
end

function P:afterLogin()
    if not self.cloud["reads" .. PlayerModel:getUid()] then
        self.cloud["reads" .. PlayerModel:getUid()] = {}
    end
    self._reads = self.cloud["reads" .. PlayerModel:getUid()]
end

function P:tryAutoPop()
    -- pop_up_type 1 每日弹一次 2 首次弹出 3 不弹出
    local dailys = LocalStore:getTableData("notice_daily_pop") or {}
    local onces = LocalStore:getTableData("notice_once_pop") or {}
    local dateStr = os.date("%Y%m%d")
    if dailys.date ~= dateStr then
        dailys.date = dateStr
        dailys.ids = {}
    end
    local notices = {}
    for _, ns in pairs(self._notices) do
        for _, v in ipairs(ns.list) do
            if v.pop_up_type == 1 then
                if table.indexof(dailys.ids, v.id) == -1 then
                    table.insert(notices, v)
                    table.insert(dailys.ids, v.id)
                end
            elseif v.pop_up_type == 2 then
                if table.indexof(onces, v.id) == -1 then
                    table.insert(notices, v)
                    table.insert(onces, v.id)
                end
            end
        end
    end
    if #notices > 0 then
        LocalStore:saveTableData("notice_daily_pop", dailys)
        LocalStore:saveTableData("notice_once_pop", onces)
        table.sort(notices, function(a, b)
            if a.notice_type ~= b.notice_type then
                return a.notice_type < b.notice_type
            end
            if a.pop_up_type ~= b.pop_up_type then
                return a.pop_up_type < b.pop_up_type
            end
            return a.id < b.id
        end)
        bee.showUiTask("Notice", {notice_type = notices[1].notice_type, id = notices[1].id}, nil, LOBBY_POP_PRIORITY.Notice)
        self._haveNew = nil
    end
end

function P:getInfo(notice_type)
    return self._notices[notice_type]
end

function P:isReaded(id)
    for _, v in ipairs(self._reads) do
        if v == id then
            return true
        end
    end
    return false
end

function P:setIsRead(id)
    for _, v in ipairs(self._reads) do
        if v == id then
            return
        end
    end
    table.insert(self._reads, id)
    self:onSave()
    self:refreshReddot()
end

function P:getUnreadTotal(notice_type)
    local ret = 0
    if notice_type then
        local info = self:getInfo(notice_type)
        for _, v in ipairs(info.list) do
            if not self:isReaded(v.id) then
                ret = ret + 1
            end
        end
    else
        for _, info in ipairs(self._notices) do
            for _, v in ipairs(info.list) do
                if not self:isReaded(v.id) then
                    ret = ret + 1
                end
            end
        end
    end
    return ret
end

function P:refreshReddot()
    RedManager:addTagWithNum(self:getUnreadTotal(self.NOTICE_TYPE.Activity), RedTag.NoticeActivity)
    RedManager:addTagWithNum(self:getUnreadTotal(self.NOTICE_TYPE.System), RedTag.NoticeSystem)
end

function P:reqNoticeList(cb)
	Net:post("notice/list", {
        t = 1,
        lang = LanguageManager:getLanguage(),
    }, function(data)
		if data.code ~= 0 then
			return
		end
        self._curLan = LanguageManager:getLanguage()
        self._haveNew = nil
        local oldIds = {}
        for _, v in ipairs(self._notices) do
            for _, d in ipairs(v.list) do
                oldIds[d.id] = oldIds[d.id]
            end
            v.list = {}
            v.total = 0
            v.unread_total = 0
        end
        if data.list then
            local minId = nil
            for _, v in ipairs(data.list) do
                local info = self._notices[v.notice_type]
                info.list[#info.list + 1] = v
                info.total = info.total + 1
                info.unread_total = info.unread_total + 1
                if not minId or minId > v.id then
                    minId = v.id
                end
                if not oldIds[v.id] and next(oldIds) then
                    self._haveNew = true
                end
            end
            for i = #self._reads, 1, -1 do
                if self._reads[i] < minId then
                    table.remove(self._reads, i)
                end
            end
            self:onSave()
            if self._haveNew and bee.isInHome() then
                self:tryAutoPop()
            end
        end

        if cb then
            cb()
        end

        self:refreshReddot()
        bee.emit(EventDef.evt_noticeRefresh)
	end)
end

return P