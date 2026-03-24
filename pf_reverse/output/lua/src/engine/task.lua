-- 队列任务
local P = class("Task")

bee.Task = P

function P:ctor(func, priority, name)
    self.func = func
    self.status = 0     -- 任务状态 0未开始 1开始 2停止
	self.tag=""
    self.name = name
    self.priority = priority or 0
end

-- 设置任务执行时长
function P:setDt(dt)
    self.dt = dt
end

function P:start()
	-- local behavior=GameManager:getStateBehavior()
	-- if behavior~=FSMStateBehavior.Idle then
	-- 	print("执行队列的时候发现 正在播其它动画")
	-- end
    self.status = 1
    if self.func then		
        self.func()
    end
end

function P:stop()
    self.status = 2
end

-- 添加一个任务 update 响应 func(dt)
function P:onUpdate(func)
    self.funcUpdate = func
end

function P:update(dt)
    if self.status == 1 then
        if self.dt then
            self.dt = self.dt - dt
            if self.dt <= 0 then
                self.dt = 0
                self.status = 2
            end
        end
        if self.funcUpdate then
            self.funcUpdate(dt, self.dt)
        end
    end
end

-- 添加一个任务
bee.addTask = function(t, TAG)
    local tasks = bee._getTasks(TAG)
    local index = 0
    for k, v in pairs(tasks) do
        if t.priority > v.priority and index == 0 and v.status == 0 then
            index = k
        end
    end
    if index == 0 then
        table.insert(tasks, t)
    else
        table.insert(tasks, index, t)
    end
    --if #tasks == 1 then --不能自動执行
        --t:start()   
    --end
    return t
end

bee.insertTask = function(t, index, TAG)
    local tasks = bee._getTasks(TAG)
    if index > #tasks then
        table.insert(tasks, t)
    else
        table.insert(tasks, index, t)
    end
    return t
end

-- 添加一个函数回调任务，TAG: 哪个任务队列 dt:自动执行下一任务的时长，-1表示取消自动
bee.addTaskFunc = function(func, dt, TAG, priority, name, index)
    local t = P:create(func, priority, name or "Func")
    if dt ~= -1 then
        t.dt = dt or 0
    end
    if index then
        return bee.insertTask(t, index, TAG)
    end
    return bee.addTask(t, TAG)
end

---- 添加一个UI 弹窗队列 关闭UI的时候自动触发一个队列
bee.showUiTask = function(uiName, params, TAG, priority, name, index)
	local popAction = function()
		if not params then
			params = {}
		end
        params.hideCb = function()
            bee.runNextTask(TAG)
        end
		params.fromTask = true
		UiManager:showUI(uiName, params)
	end
	return bee.addTaskFunc(popAction, -1, TAG, priority, name or uiName, index)
end

bee.existTask = function(TAG)
    local tasks = bee._getTasks(TAG)
	if #tasks > 0 then
        return true
    end
    return false
end

-- 是否存在xxx优先级的任务
bee.existPriorityTask = function(TAG, priority)
    local tasks = bee._getTasks(TAG)
	if #tasks > 0 then
        for _, v in pairs(tasks) do
            if v.priority == priority then
                return true
            end
        end
    end
    return false
end

-- 存在除了xxx优先级的其他未执行任务
bee.existPriorityTaskExcept = function(TAG, priority, status)
    local tasks = bee._getTasks(TAG)
    status = status or 0    --未执行的任务
	if #tasks > 0 then
        for _, v in pairs(tasks) do
            if v.priority ~= priority and v.status == status then
                return true
            end
        end
    end
    return false
end

--只有{xxx}优先级的任务
bee.onlyPriorityTask = function(TAG, priorityList, status)
    local tasks = bee._getTasks(TAG)
    status = status or 0    --未执行的任务
	if #tasks > 0 then
        for _, v in pairs(tasks) do
            if not table.contains(priorityList, v.priority) and v.status == status then
                return false
            end
        end
    end
    return true
end

--存在min优先级到max优先级的未执行任务
bee.existPriorityTaskBetween = function(TAG, maxPriority, minPriority, status) 
    local tasks = bee._getTasks(TAG)
    status = status or 0    --未执行的任务
	if #tasks > 0 then
        for _, v in pairs(tasks) do
            if v.priority <= maxPriority or v.priority >= minPriority and v.status == status then
                return true
            end
        end
    end
    return false
end

bee.runTask = function(TAG)
	local tasks = bee._getTasks(TAG)
	if #tasks > 0 then
		if tasks[1].status==0 then
			tasks[1]:start()
		else
			print("任务已经在执行")
		end
	end
end

bee.removeTaskByPriority = function(priority, TAG)
    if not bee._tasks then return end
    local tasks = bee._getTasks(TAG)
    if #tasks > 0 then
        for i = #tasks, 1, -1 do
            if tasks[i].priority == priority and 0 == tasks[i].status then
                table.remove(tasks, i)
            end
        end
    end
end

bee.removeTasks = function(TAG)
    if not bee._tasks then return end
    if not TAG then
        TAG = "TASK_GLOBAL"
    end
    if bee._tasks[TAG] then
        bee._tasks[TAG] = nil
    end
end

bee.removeAllTasks = function(TAG)
    if bee._tasks then
        bee._tasks = nil
    end
end

-- 结束当前任务，执行下一个任务
bee.runNextTask = function(TAG)
    local tasks = bee._getTasks(TAG)
    if #tasks > 0 then
        local t = table.remove(tasks, 1)
        t.status = 2
        if #tasks > 0 and tasks[1].status ~= 2 then
            tasks[1]:start()
        end
    end
end

bee._getTasks = function(TAG)
    if not TAG then
        TAG = "TASK_GLOBAL"
    end
    if not bee._tasks then
        bee._tasks = {TASK_GLOBAL = {}}
    end
    local tasks = bee._tasks[TAG]
    if not tasks then
        tasks = {}
        bee._tasks[TAG] = tasks
    end
    return tasks
end

bee._updateTask = function(dt)
    if not bee._tasks then return end
    for _, v in pairs(bee._tasks) do
        if #v > 0 then
            v[1]:update(dt)
        end
    end
    for _, v in pairs(bee._tasks) do
        if #v > 0 then
            if v[1].status == 2 then
                table.remove(v, 1)
                if #v > 0 and v[1].state ~= 2 then
                    v[1]:start()
                end
            end
        end
    end
end

bee.checkShowUI = function(uiName, params, TAG, priority)
	if bee.existTask() then
		bee.showUiTask(uiName, params, TAG, priority or Config.TaskPriority.ActivityClick)
	else
		UiManager:showUI(uiName, params)
	end
end

bee.checkAddTaskFunc = function(func, dt, TAG, priority, name)
	if bee.existTask() then
		bee.addTaskFunc(func, dt, TAG, priority, name)
	else
		if func then
			func()
		end
	end
end

bee.checkAddDelayTask = function(delay, cb, TAG, priority)
	if bee.existTask() then
		bee.addTaskFunc(function()
			bee.once(delay, function() 
				if cb then
					cb()
				end
				bee.runNextTask()
			end)
		end, TAG, priority or Config.TaskPriority.ActivityClick)
	else
		bee.once(delay, function() 
			if cb then
				cb()
			end
		end)
	end
