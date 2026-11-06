-- 派遣历史记录弹窗
-- 显示派遣的历史数据，可通过TabFilter筛选全部/派遣中/已完成
-- 列表元素：事务名、等级图标、人数、开始时间、阵营图标
local P = class("DispatchSideRecord", UiBase)

-- 模拟 reqRecordList 的合并逻辑：首条记录为 base，所有记录放入 roles
local function mergeRecords(records)
    if not records or #records == 0 then
        return nil
    end
    local base = records[1]
    base.roles = {}
    for _, r in ipairs(records) do
        table.insert(base.roles, r)
    end
    return base
end

function P:onAwake()
    local RecordMain = self:find("AnimRoot/Left/Record/RecordMain")
    local Main = self:find("Main", RecordMain)

    -- 筛选下拉框
    self.TabFilter = self:find("TabFilter", Main)
    self.TabFilterItem = self:find("TabFilterItem", self.TabFilter)

    -- 列表
    self.RecordList = self:find("RecordList", Main)
    self.Item01 = self:find("Item01", self.RecordList)
    self.Item01:SetActive(false)

    -- 空状态
    self.Empty = self:find("Empty", Main)

    -- 关闭按钮
    bee.addClick(self:find("CloseButton", RecordMain), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("Mask"), function()
        self:hideUI()
    end)

    self.Filter = UiFilterBox:create(self.TabFilter, self.TabFilterItem, self.node)
    self.Filter:setDatas({
        _T("TAB_SHOP_THEME_3"),    -- 全部
        _T("LAB_DISPATCH_60"),     -- 派遣中...
        _T("LAB_DISPATCH_27"),     -- 已完成
    })
    self.Filter:setSelectFunc(function(idx, data)
        if self._filterIdx ~= idx then
            bee.logEvent("dispatch-history-filter", idx)
            self._filterIdx = idx
            self:setSelectData()
            self:refreshList()
        end
    end)

    -- 初始化列表
    self.List = UiListEx:create(self.RecordList)
    self.List:setWidth(201)
    self.List:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.Item01)
    end)
    self.List:setRefreshFunc(function(data, item, isInit, index)
        self:setRecordItem(data, item, isInit, index)
    end)
    self.List:setScrollToBottomFunc(function()
        DispatchModel:reqRecordList(function(record_list)
            if not bee.isNull(self.node) then

                self:refreshList(record_list)
            end
        end)
    end)
end

function P:onShow()
    self._filterIdx = 1
    self._selectData = nil
    if self.Filter then
        self.Filter:setSelectIdx(1)
    end

    DispatchModel:reqRecordList(function(record_list)
        if not bee.isNull(self.node) then

            self:refreshList()
        end
    end, true)
    -- self:refreshList()
end

function P:refreshList(record_list)
    local datas = {}

    -- 遍历所有阵营的事件列表，收集历史记录
    for _, v in pairs(record_list or DispatchModel._record_list) do
        local status = v.status
        for _, r in ipairs(v.roles) do
            if 1 == r.status then
                status = r.status
            end
        end
        v.real_status = status
        if self._filterIdx == 1 or (self._filterIdx == 2 and status == 1) or (self._filterIdx == 3 and status ~= 1) then
            table.insert(datas, v)
        end
    end

    -- table.sort(datas, function(a, b)
    --     if a.real_status ~= b.real_status then
    --         if a.real_status == 1 then
    --             return true
    --         end
    --         if b.real_status == 1 then
    --             return false
    --         end
    --     end
    --     if a.start_ts ~= b.start_ts then
    --         return a.start_ts > b.start_ts
    --     end
    --     return (a.event_id or 0) > (b.event_id or 0)
    -- end)

    if record_list then
        self.List:append(datas)
    else
        self.List:setDatas(datas)
    end
    self.Empty:SetActive(self.List:getDatas() == 0)
end

function P:setRecordItem(data, item, isInit, index)
    local Ani_root = self:find("Ani_root", item)

    if isInit and index > 0 then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_DispatchStar_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_DispatchStar_item_idle", Ani_root)
    end

    local Information = self:find("Information", Ani_root)
    
    local status = data.status
    for _, r in ipairs(data.roles) do
        if 1 == r.status then
            status = r.status
        end
    end

    -- 等级背景
    bee.setIcon(self:find("Frame/FrameLevel/dispatch_side_record_task_bg_01", Ani_root), "dispatch_side_record_task_bg_0" .. data.event_level, "Dispatch")
    self:find("Frame/FrameState/dispatch_side_record_task_state_bg_02", Ani_root):SetActive(1 == status)
    self:find("Frame/FrameState/dispatch_side_record_task_state_bg_01", Ani_root):SetActive(1 ~= status)

    -- 等级图标
    bee.setIcon(self:find("TaskLevel/dispatch_main_directory_task_level_01", Information), "dispatch_main_directory_task_level_0" .. data.event_level, "Dispatch", true)

    -- 事务名
    local eventCfg = tpl_event_info[data.event_id]
    bee.setText(self:find("TextName", Information), _T(eventCfg.event_name))

    -- 阵营图标
    local campCfg = tpl_camp_detail[data.event_camp]
    if campCfg then
        bee.setIconInAtlas(self:find("CampIcon/dispatch_main_camp_0", Information), campCfg.camp_icon)
    end

    -- 派遣人数
    bee.setText(self:find("Quantity/TextNum", Information), "x" .. (#data.roles))
    self:find("State/TextState2", Information):SetActive(1 == status)
    self:find("State/TextState1", Information):SetActive(1 ~= status)

    bee.setText(self:find("Time/Text/TextTime", Ani_root), TimeHelp:getDateTimeStr(data.start_ts))

    self:find("dispatch_side_record_task_bg_on", Ani_root):SetActive(self._selectData == data)

    -- 点击查看详情
    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        self:setSelectData(data, item)
        UiManager:showUI("DispatchSideRecordTips", {data = data, target = item})
    end, true)
end

function P:setSelectData(data, item)
    if self._selectItem then
        self:find("Ani_root/dispatch_side_record_task_bg_on", self._selectItem):SetActive(false)    
    end
    self._selectData = data
    self._selectItem = item
    if item then
        self:find("Ani_root/dispatch_side_record_task_bg_on", item):SetActive(self._selectData == data)
    end
end

return P