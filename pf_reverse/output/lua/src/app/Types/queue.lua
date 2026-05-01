local queue = class("queue")

function queue:ctor()
	self:reset()
end

function queue:reset()
	self.table = {}
	self.startIndex = 0
	self.endIndex = 0
end

function queue:size()
	return self.endIndex - self.startIndex
end

function queue:push(item)
	self.endIndex = self.endIndex + 1
	self.table[self.endIndex] = item
end

function queue:pop()
	if self:size() <= 0 then
		return nil
	end
	self.startIndex = self.startIndex + 1
	local item = self.table[self.startIndex]
	return item
end

function queue:iter()
	local i = self.startIndex
	return function ()
		i = i + 1
		if i <= self.endIndex then
			return self.table[i]
		end
	end
end
return queue